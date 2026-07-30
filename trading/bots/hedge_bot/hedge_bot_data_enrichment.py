# trading/bots/hedge_bot/hedge_bot_data_enrichment.py
# Advanced Data Enrichment & Feature Engineering for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Enrichment Module - Module d'enrichissement de données avancé pour le Hedge Bot.
Fournit des fonctionnalités d'enrichissement de données, d'ingénierie de features, de calcul d'indicateurs
techniques avancés et de transformation de données pour l'optimisation des décisions de hedging.
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
import hashlib
import pickle

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_enrichment")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    DecisionContext, MarketRegime
)


# ============== ENUMS & TYPES ==============

class EnrichmentType(Enum):
    """Types d'enrichissement de données."""
    TECHNICAL_INDICATORS = "technical_indicators"
    FEATURE_ENGINEERING = "feature_engineering"
    MARKET_DATA = "market_data"
    FUNDAMENTAL_DATA = "fundamental_data"
    SENTIMENT_DATA = "sentiment_data"
    DERIVED_DATA = "derived_data"
    AGGREGATED_DATA = "aggregated_data"
    NORMALIZED_DATA = "normalized_data"
    TRANSFORMED_DATA = "transformed_data"
    SEQUENTIAL_DATA = "sequential_data"
    PATTERN_DATA = "pattern_data"
    VOLATILITY_DATA = "volatility_data"


class IndicatorCategory(Enum):
    """Catégories d'indicateurs techniques."""
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    CYCLE = "cycle"
    PATTERN = "pattern"
    CUSTOM = "custom"


class FeatureType(Enum):
    """Types de features."""
    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    TEXTUAL = "textual"
    SEQUENTIAL = "sequential"
    HIGH_DIMENSIONAL = "high_dimensional"


# ============== DATA MODELS ==============

@dataclass
class EnrichedData:
    """Données enrichies avec métadonnées."""
    enriched_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_data: Any = None
    enriched_data: Any = None
    enrichment_type: EnrichmentType = EnrichmentType.TECHNICAL_INDICATORS
    features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    version: int = 1
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "enriched_id": self.enriched_id,
            "enrichment_type": self.enrichment_type.value,
            "features": self.features,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "version": self.version,
            "tags": self.tags,
            "correlation_id": self.correlation_id
        }


@dataclass
class TechnicalIndicator:
    """Indicateur technique."""
    indicator_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: IndicatorCategory = IndicatorCategory.TREND
    value: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.0
    signal: str = "neutral"  # buy, sell, neutral
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "indicator_id": self.indicator_id,
            "name": self.name,
            "category": self.category.value,
            "value": self.value,
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "signal": self.signal,
            "metadata": self.metadata
        }


@dataclass
class FeatureSet:
    """Ensemble de features."""
    feature_set_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    features: Dict[str, Any] = field(default_factory=dict)
    feature_types: Dict[str, FeatureType] = field(default_factory=dict)
    importance: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


# ============== INTERFACES ==============

class EnrichmentEngineInterface(ABC):
    """Interface abstraite pour le moteur d'enrichissement."""
    
    @abstractmethod
    async def enrich(
        self,
        data: Any,
        enrichment_type: EnrichmentType,
        parameters: Optional[Dict[str, Any]] = None
    ) -> EnrichedData:
        """Enrichit des données."""
        pass
    
    @abstractmethod
    async def get_features(
        self,
        data: Any,
        feature_names: Optional[List[str]] = None
    ) -> FeatureSet:
        """Extrait des features."""
        pass


# ============== IMPLÉMENTATIONS ==============

class EnrichmentEngine(EnrichmentEngineInterface):
    """
    Moteur d'enrichissement de données avancé.
    Calcule des indicateurs techniques, extrait des features, et enrichit les données
    pour l'optimisation des décisions de hedging.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache des indicateurs
        self._indicator_cache: Dict[str, TechnicalIndicator] = {}
        self._cache_lock = threading.RLock()
        
        # Cache des features
        self._feature_cache: Dict[str, FeatureSet] = {}
        self._feature_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "enrichments": 0,
            "feature_extractions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        logger.info("EnrichmentEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "cache_size": 1000,
            "cache_ttl": 3600,  # 1 heure
            "enable_caching": True,
            "parallel_computation": True,
            "default_window": 20,
            "default_period": 14
        }
    
    async def enrich(
        self,
        data: Any,
        enrichment_type: EnrichmentType,
        parameters: Optional[Dict[str, Any]] = None
    ) -> EnrichedData:
        """Enrichit des données."""
        self._stats["enrichments"] += 1
        parameters = parameters or {}
        
        try:
            # Vérification du cache
            cache_key = self._compute_cache_key(data, enrichment_type, parameters)
            if self.config["enable_caching"] and cache_key in self._indicator_cache:
                self._stats["cache_hits"] += 1
                cached = self._indicator_cache[cache_key]
                return EnrichedData(
                    original_data=data,
                    enriched_data=cached.to_dict(),
                    enrichment_type=enrichment_type,
                    features=cached.metadata,
                    source="cache"
                )
            
            self._stats["cache_misses"] += 1
            
            # Enrichissement selon le type
            if enrichment_type == EnrichmentType.TECHNICAL_INDICATORS:
                enriched = await self._enrich_technical_indicators(data, parameters)
            elif enrichment_type == EnrichmentType.FEATURE_ENGINEERING:
                enriched = await self._enrich_feature_engineering(data, parameters)
            elif enrichment_type == EnrichmentType.MARKET_DATA:
                enriched = await self._enrich_market_data(data, parameters)
            elif enrichment_type == EnrichmentType.SENTIMENT_DATA:
                enriched = await self._enrich_sentiment_data(data, parameters)
            elif enrichment_type == EnrichmentType.VOLATILITY_DATA:
                enriched = await self._enrich_volatility_data(data, parameters)
            else:
                enriched = data
            
            # Création de l'objet enrichi
            result = EnrichedData(
                original_data=data,
                enriched_data=enriched,
                enrichment_type=enrichment_type,
                features=await self._extract_features(enriched),
                source="enrichment_engine"
            )
            
            # Mise en cache
            if self.config["enable_caching"]:
                with self._cache_lock:
                    if len(self._indicator_cache) < self.config["cache_size"]:
                        self._indicator_cache[cache_key] = TechnicalIndicator(
                            name=enrichment_type.value,
                            value=1.0,
                            metadata=result.features
                        )
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Enrichment error: {e}")
            raise
    
    async def get_features(
        self,
        data: Any,
        feature_names: Optional[List[str]] = None
    ) -> FeatureSet:
        """Extrait des features."""
        self._stats["feature_extractions"] += 1
        
        try:
            # Extraction des features
            features = await self._extract_features(data)
            
            # Filtrage
            if feature_names:
                features = {k: v for k, v in features.items() if k in feature_names}
            
            # Création du FeatureSet
            feature_set = FeatureSet(
                name=f"features_{uuid.uuid4().hex[:8]}",
                features=features,
                feature_types=await self._infer_feature_types(features)
            )
            
            return feature_set
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Feature extraction error: {e}")
            raise
    
    # ========== MÉTHODES PRIVÉES - ENRICHISSEMENT ==========
    
    async def _enrich_technical_indicators(
        self,
        data: Any,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcule les indicateurs techniques."""
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        
        window = parameters.get("window", self.config["default_window"])
        period = parameters.get("period", self.config["default_period"])
        
        indicators = {}
        
        # Vérification des colonnes nécessaires
        if 'close' not in data.columns:
            logger.warning("No 'close' column found, using first numeric column")
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                data['close'] = data[numeric_cols[0]]
            else:
                return indicators
        
        # Calcul des indicateurs
        # 1. Moving Averages
        indicators['sma_10'] = data['close'].rolling(window=10).mean().iloc[-1] if len(data) >= 10 else 0
        indicators['sma_20'] = data['close'].rolling(window=20).mean().iloc[-1] if len(data) >= 20 else 0
        indicators['sma_50'] = data['close'].rolling(window=50).mean().iloc[-1] if len(data) >= 50 else 0
        indicators['ema_12'] = data['close'].ewm(span=12, adjust=False).mean().iloc[-1] if len(data) >= 12 else 0
        indicators['ema_26'] = data['close'].ewm(span=26, adjust=False).mean().iloc[-1] if len(data) >= 26 else 0
        
        # 2. RSI (Relative Strength Index)
        if len(data) >= period + 1:
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            indicators['rsi'] = 100 - (100 / (1 + rs.iloc[-1])) if len(rs) > 0 else 50
        else:
            indicators['rsi'] = 50
        
        # 3. MACD (Moving Average Convergence Divergence)
        if len(data) >= 26:
            exp1 = data['close'].ewm(span=12, adjust=False).mean()
            exp2 = data['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            indicators['macd'] = macd.iloc[-1] if len(macd) > 0 else 0
            indicators['macd_signal'] = signal.iloc[-1] if len(signal) > 0 else 0
            indicators['macd_histogram'] = (macd - signal).iloc[-1] if len(macd) > 0 and len(signal) > 0 else 0
        else:
            indicators['macd'] = 0
            indicators['macd_signal'] = 0
            indicators['macd_histogram'] = 0
        
        # 4. Bollinger Bands
        if len(data) >= window:
            sma = data['close'].rolling(window=window).mean()
            std = data['close'].rolling(window=window).std()
            indicators['bollinger_upper'] = (sma + 2 * std).iloc[-1] if len(sma) > 0 else 0
            indicators['bollinger_middle'] = sma.iloc[-1] if len(sma) > 0 else 0
            indicators['bollinger_lower'] = (sma - 2 * std).iloc[-1] if len(sma) > 0 else 0
            indicators['bollinger_position'] = (
                (data['close'].iloc[-1] - indicators['bollinger_lower']) / 
                (indicators['bollinger_upper'] - indicators['bollinger_lower'])
                if indicators['bollinger_upper'] != indicators['bollinger_lower'] else 0.5
            )
        else:
            indicators['bollinger_upper'] = 0
            indicators['bollinger_middle'] = 0
            indicators['bollinger_lower'] = 0
            indicators['bollinger_position'] = 0.5
        
        # 5. Momentum
        if len(data) >= period:
            indicators['momentum'] = (data['close'].iloc[-1] / data['close'].iloc[-period] - 1) * 100
        else:
            indicators['momentum'] = 0
        
        # 6. Volatility
        if len(data) >= window:
            indicators['volatility'] = data['close'].pct_change().rolling(window=window).std().iloc[-1] * 100
        else:
            indicators['volatility'] = 0
        
        # 7. Volume indicators
        if 'volume' in data.columns and len(data) >= window:
            indicators['volume_ma'] = data['volume'].rolling(window=window).mean().iloc[-1]
            indicators['volume_ratio'] = data['volume'].iloc[-1] / indicators['volume_ma'] if indicators['volume_ma'] > 0 else 1
        else:
            indicators['volume_ma'] = 0
            indicators['volume_ratio'] = 1
        
        # 8. ATR (Average True Range)
        if len(data) >= period and 'high' in data.columns and 'low' in data.columns:
            high = data['high']
            low = data['low']
            close = data['close']
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            indicators['atr'] = tr.rolling(window=period).mean().iloc[-1]
        else:
            indicators['atr'] = 0
        
        # 9. Stochastic Oscillator
        if len(data) >= period and 'high' in data.columns and 'low' in data.columns:
            high_max = data['high'].rolling(window=period).max()
            low_min = data['low'].rolling(window=period).min()
            indicators['stochastic_k'] = (
                (data['close'].iloc[-1] - low_min.iloc[-1]) / 
                (high_max.iloc[-1] - low_min.iloc[-1]) * 100
                if high_max.iloc[-1] != low_min.iloc[-1] else 50
            )
            # %D = SMA de %K sur 3 périodes
            k_values = []
            for i in range(min(3, len(data))):
                k = (
                    (data['close'].iloc[-(i+1)] - low_min.iloc[-(i+1)]) /
                    (high_max.iloc[-(i+1)] - low_min.iloc[-(i+1)]) * 100
                    if high_max.iloc[-(i+1)] != low_min.iloc[-(i+1)] else 50
                )
                k_values.append(k)
            indicators['stochastic_d'] = sum(k_values) / len(k_values) if k_values else 50
        else:
            indicators['stochastic_k'] = 50
            indicators['stochastic_d'] = 50
        
        # 10. Signal interprétation
        indicators['signal'] = self._interpret_signals(indicators)
        
        return indicators
    
    async def _enrich_feature_engineering(
        self,
        data: Any,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrichit avec de l'ingénierie de features."""
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        
        features = {}
        
        # 1. Lag features
        lag_periods = parameters.get("lag_periods", [1, 2, 3, 5, 10])
        for lag in lag_periods:
            if len(data) > lag:
                features[f'close_lag_{lag}'] = data['close'].shift(lag).iloc[-1]
        
        # 2. Rolling statistics
        windows = parameters.get("windows", [5, 10, 20])
        for w in windows:
            if len(data) >= w:
                features[f'roll_mean_{w}'] = data['close'].rolling(w).mean().iloc[-1]
                features[f'roll_std_{w}'] = data['close'].rolling(w).std().iloc[-1]
                features[f'roll_max_{w}'] = data['close'].rolling(w).max().iloc[-1]
                features[f'roll_min_{w}'] = data['close'].rolling(w).min().iloc[-1]
        
        # 3. Rate of change
        roc_periods = parameters.get("roc_periods", [1, 5, 10])
        for p in roc_periods:
            if len(data) > p:
                features[f'roc_{p}'] = (data['close'].iloc[-1] / data['close'].iloc[-(p+1)] - 1) * 100
        
        # 4. Exponential smoothing
        if len(data) >= 10:
            features['exp_smooth_0.1'] = data['close'].ewm(alpha=0.1).mean().iloc[-1]
            features['exp_smooth_0.3'] = data['close'].ewm(alpha=0.3).mean().iloc[-1]
        
        # 5. Price features
        if 'high' in data.columns and 'low' in data.columns:
            features['high_low_ratio'] = data['high'].iloc[-1] / data['low'].iloc[-1]
            features['close_high_ratio'] = data['close'].iloc[-1] / data['high'].iloc[-1]
            features['close_low_ratio'] = data['close'].iloc[-1] / data['low'].iloc[-1]
        
        # 6. Volume features
        if 'volume' in data.columns and len(data) >= 10:
            features['volume_mean_10'] = data['volume'].rolling(10).mean().iloc[-1]
            features['volume_std_10'] = data['volume'].rolling(10).std().iloc[-1]
            features['volume_roc_5'] = (data['volume'].iloc[-1] / data['volume'].iloc[-6] - 1) * 100 if len(data) > 5 else 0
        
        return features
    
    async def _enrich_market_data(
        self,
        data: Any,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrichit avec des données de marché."""
        market_data = {}
        
        if isinstance(data, dict):
            # Extraction des données de marché
            market_data['price'] = data.get('price', 0)
            market_data['volume'] = data.get('volume', 0)
            market_data['market_cap'] = data.get('market_cap', 0)
            market_data['pe_ratio'] = data.get('pe_ratio', 0)
            market_data['dividend_yield'] = data.get('dividend_yield', 0)
            market_data['beta'] = data.get('beta', 0)
        
        return market_data
    
    async def _enrich_sentiment_data(
        self,
        data: Any,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrichit avec des données de sentiment."""
        sentiment_data = {
            'sentiment_score': 0.0,
            'bullish_ratio': 0.0,
            'bearish_ratio': 0.0,
            'neutral_ratio': 0.0,
            'social_volume': 0,
            'news_sentiment': 0.0
        }
        
        if isinstance(data, dict):
            # Extraction des données de sentiment
            sentiment_data['sentiment_score'] = data.get('sentiment', 0.0)
            sentiment_data['social_volume'] = data.get('social_volume', 0)
            sentiment_data['news_sentiment'] = data.get('news_sentiment', 0.0)
        
        # Normalisation
        if sentiment_data['sentiment_score'] > 0.3:
            sentiment_data['bullish_ratio'] = sentiment_data['sentiment_score']
        elif sentiment_data['sentiment_score'] < -0.3:
            sentiment_data['bearish_ratio'] = -sentiment_data['sentiment_score']
        else:
            sentiment_data['neutral_ratio'] = 1 - abs(sentiment_data['sentiment_score'])
        
        return sentiment_data
    
    async def _enrich_volatility_data(
        self,
        data: Any,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enrichit avec des données de volatilité."""
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        
        window = parameters.get("window", self.config["default_window"])
        
        volatility_data = {}
        
        if 'close' in data.columns and len(data) >= window:
            returns = data['close'].pct_change()
            
            # Volatilité historique
            volatility_data['historical_volatility'] = returns.std() * np.sqrt(252)
            
            # Volatilité réalisée
            volatility_data['realized_volatility'] = returns.rolling(window).std().iloc[-1] * np.sqrt(252)
            
            # Volatilité de Parkinson (High-Low)
            if 'high' in data.columns and 'low' in data.columns:
                log_hl = np.log(data['high'] / data['low'])
                volatility_data['parkinson_volatility'] = log_hl.rolling(window).std().iloc[-1] * np.sqrt(252)
            
            # Volatilité de Garman-Klass (OHLC)
            if all(c in data.columns for c in ['open', 'high', 'low', 'close']):
                log_hl = np.log(data['high'] / data['low'])
                log_co = np.log(data['close'] / data['open'])
                vol_squared = (0.5 * log_hl**2 - (2*np.log(2) - 1) * log_co**2)
                volatility_data['garman_klass_volatility'] = np.sqrt(vol_squared.rolling(window).mean().iloc[-1]) * np.sqrt(252)
        
        return volatility_data
    
    # ========== MÉTHODES PRIVÉES - FEATURES ==========
    
    async def _extract_features(self, data: Any) -> Dict[str, Any]:
        """Extrait des features des données."""
        features = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    features[key] = value
                elif isinstance(value, dict):
                    sub_features = await self._extract_features(value)
                    features.update({f"{key}_{k}": v for k, v in sub_features.items()})
        
        elif isinstance(data, pd.DataFrame):
            for col in data.columns:
                if data[col].dtype in [np.float64, np.int64]:
                    features[f"{col}_last"] = data[col].iloc[-1] if len(data) > 0 else 0
                    features[f"{col}_mean"] = data[col].mean()
                    features[f"{col}_std"] = data[col].std()
                    features[f"{col}_min"] = data[col].min()
                    features[f"{col}_max"] = data[col].max()
        
        elif isinstance(data, list) and data and isinstance(data[0], (int, float)):
            features['list_mean'] = np.mean(data)
            features['list_std'] = np.std(data)
            features['list_min'] = np.min(data)
            features['list_max'] = np.max(data)
            features['list_median'] = np.median(data)
        
        return features
    
    async def _infer_feature_types(
        self,
        features: Dict[str, Any]
    ) -> Dict[str, FeatureType]:
        """Infère les types des features."""
        types = {}
        
        for key, value in features.items():
            if isinstance(value, (int, float)):
                types[key] = FeatureType.NUMERICAL
            elif isinstance(value, str):
                types[key] = FeatureType.CATEGORICAL
            elif isinstance(value, bool):
                types[key] = FeatureType.CATEGORICAL
            elif isinstance(value, (list, np.ndarray)):
                types[key] = FeatureType.SEQUENTIAL
            elif isinstance(value, datetime):
                types[key] = FeatureType.TEMPORAL
            else:
                types[key] = FeatureType.HIGH_DIMENSIONAL
        
        return types
    
    def _interpret_signals(self, indicators: Dict[str, Any]) -> str:
        """Interprète les signaux des indicateurs."""
        # Analyse du RSI
        rsi = indicators.get('rsi', 50)
        rsi_signal = 'buy' if rsi < 30 else 'sell' if rsi > 70 else 'neutral'
        
        # Analyse du MACD
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_hist = indicators.get('macd_histogram', 0)
        macd_signal_value = 'buy' if macd > macd_signal and macd_hist > 0 else 'sell' if macd < macd_signal and macd_hist < 0 else 'neutral'
        
        # Analyse des Bollinger Bands
        bb_pos = indicators.get('bollinger_position', 0.5)
        bb_signal = 'buy' if bb_pos < 0.2 else 'sell' if bb_pos > 0.8 else 'neutral'
        
        # Analyse du Momentum
        momentum = indicators.get('momentum', 0)
        momentum_signal = 'buy' if momentum > 0 else 'sell' if momentum < 0 else 'neutral'
        
        # Agrégation des signaux
        signals = {
            'rsi': 1 if rsi_signal == 'buy' else -1 if rsi_signal == 'sell' else 0,
            'macd': 1 if macd_signal_value == 'buy' else -1 if macd_signal_value == 'sell' else 0,
            'bb': 1 if bb_signal == 'buy' else -1 if bb_signal == 'sell' else 0,
            'momentum': 1 if momentum_signal == 'buy' else -1 if momentum_signal == 'sell' else 0
        }
        
        # Signal global
        total = sum(signals.values())
        if total >= 2:
            return 'buy'
        elif total <= -2:
            return 'sell'
        else:
            return 'neutral'
    
    def _compute_cache_key(
        self,
        data: Any,
        enrichment_type: EnrichmentType,
        parameters: Dict[str, Any]
    ) -> str:
        """Calcule une clé de cache unique."""
        # Hash des données
        data_hash = hashlib.md5(str(data).encode()).hexdigest()[:8]
        params_hash = hashlib.md5(json.dumps(parameters, sort_keys=True).encode()).hexdigest()[:8]
        return f"{enrichment_type.value}_{data_hash}_{params_hash}"
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._cache_lock:
            self._stats["cache_size"] = len(self._indicator_cache)
        return self._stats
    
    async def clear_cache(self) -> None:
        """Vide le cache."""
        with self._cache_lock:
            self._indicator_cache.clear()
        with self._feature_lock:
            self._feature_cache.clear()
        logger.info("EnrichmentEngine cache cleared")


# ============== TECHNICAL INDICATOR LIBRARY ==============

class TechnicalIndicatorLibrary:
    """
    Bibliothèque d'indicateurs techniques avancés.
    Fournit une collection complète d'indicateurs techniques pour l'analyse de marché.
    """
    
    def __init__(self):
        self._indicators: Dict[str, Callable] = {}
        self._register_indicators()
    
    def _register_indicators(self) -> None:
        """Enregistre les indicateurs disponibles."""
        # Trend Indicators
        self._indicators['sma'] = self._sma
        self._indicators['ema'] = self._ema
        self._indicators['macd'] = self._macd
        self._indicators['adx'] = self._adx
        self._indicators['ichimoku'] = self._ichimoku
        self._indicators['parabolic_sar'] = self._parabolic_sar
        
        # Momentum Indicators
        self._indicators['rsi'] = self._rsi
        self._indicators['stochastic'] = self._stochastic
        self._indicators['cci'] = self._cci
        self._indicators['mfi'] = self._mfi
        self._indicators['williams_r'] = self._williams_r
        
        # Volatility Indicators
        self._indicators['bollinger_bands'] = self._bollinger_bands
        self._indicators['atr'] = self._atr
        self._indicators['keltner_channels'] = self._keltner_channels
        self._indicators['donchian_channels'] = self._donchian_channels
        
        # Volume Indicators
        self._indicators['obv'] = self._obv
        self._indicators['vwap'] = self._vwap
        self._indicators['money_flow'] = self._money_flow
        self._indicators['chaikin_oscillator'] = self._chaikin_oscillator
    
    def get_indicator(self, name: str) -> Optional[Callable]:
        """Récupère un indicateur par son nom."""
        return self._indicators.get(name)
    
    def list_indicators(self) -> List[str]:
        """Liste tous les indicateurs disponibles."""
        return list(self._indicators.keys())
    
    # ========== INDICATEURS DE TENDANCE ==========
    
    @staticmethod
    def _sma(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Simple Moving Average."""
        return data['close'].rolling(window=period).mean().values
    
    @staticmethod
    def _ema(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Exponential Moving Average."""
        return data['close'].ewm(span=period, adjust=False).mean().values
    
    @staticmethod
    def _macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """MACD (Moving Average Convergence Divergence)."""
        exp1 = data['close'].ewm(span=fast, adjust=False).mean()
        exp2 = data['close'].ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return {
            'macd': macd.values,
            'signal': signal_line.values,
            'histogram': histogram.values
        }
    
    @staticmethod
    def _adx(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """ADX (Average Directional Index)."""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Directional Movement
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smoothing
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx.values
    
    @staticmethod
    def _ichimoku(data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Ichimoku Cloud."""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # Tenkan-sen (Conversion Line)
        tenkan_sen = (high.rolling(window=9).max() + low.rolling(window=9).min()) / 2
        
        # Kijun-sen (Base Line)
        kijun_sen = (high.rolling(window=26).max() + low.rolling(window=26).min()) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        # Senkou Span B (Leading Span B)
        senkou_b = ((high.rolling(window=52).max() + low.rolling(window=52).min()) / 2).shift(26)
        
        # Chikou Span (Lagging Span)
        chikou_span = close.shift(-26)
        
        return {
            'tenkan_sen': tenkan_sen.values,
            'kijun_sen': kijun_sen.values,
            'senkou_a': senkou_a.values,
            'senkou_b': senkou_b.values,
            'chikou_span': chikou_span.values
        }
    
    @staticmethod
    def _parabolic_sar(data: pd.DataFrame, step: float = 0.02, max_step: float = 0.2) -> np.ndarray:
        """Parabolic SAR."""
        high = data['high']
        low = data['low']
        
        sar = np.zeros(len(data))
        trend = np.ones(len(data))  # 1: uptrend, -1: downtrend
        af = step * np.ones(len(data))
        
        if len(data) > 0:
            sar[0] = low[0]
            trend[0] = 1
            
            for i in range(1, len(data)):
                if trend[i-1] == 1:
                    sar[i] = sar[i-1] + af[i-1] * (high[i-1] - sar[i-1])
                    if high[i] > high[i-1]:
                        af[i] = min(af[i-1] + step, max_step)
                    else:
                        af[i] = af[i-1]
                    if low[i] < sar[i]:
                        trend[i] = -1
                        sar[i] = high[i-1]
                        af[i] = step
                    else:
                        trend[i] = 1
                else:
                    sar[i] = sar[i-1] - af[i-1] * (low[i-1] - sar[i-1])
                    if low[i] < low[i-1]:
                        af[i] = min(af[i-1] + step, max_step)
                    else:
                        af[i] = af[i-1]
                    if high[i] > sar[i]:
                        trend[i] = 1
                        sar[i] = low[i-1]
                        af[i] = step
                    else:
                        trend[i] = -1
        
        return sar
    
    # ========== INDICATEURS DE MOMENTUM ==========
    
    @staticmethod
    def _rsi(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """RSI (Relative Strength Index)."""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values
    
    @staticmethod
    def _stochastic(data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, np.ndarray]:
        """Stochastic Oscillator."""
        high_max = data['high'].rolling(window=k_period).max()
        low_min = data['low'].rolling(window=k_period).min()
        k = 100 * (data['close'] - low_min) / (high_max - low_min)
        d = k.rolling(window=d_period).mean()
        return {'k': k.values, 'd': d.values}
    
    @staticmethod
    def _cci(data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """CCI (Commodity Channel Index)."""
        tp = (data['high'] + data['low'] + data['close']) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        cci = (tp - sma) / (0.015 * mad)
        return cci.values
    
    @staticmethod
    def _mfi(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """MFI (Money Flow Index)."""
        tp = (data['high'] + data['low'] + data['close']) / 3
        money_flow = tp * data['volume']
        positive_flow = money_flow.where(tp > tp.shift(), 0).rolling(window=period).sum()
        negative_flow = money_flow.where(tp < tp.shift(), 0).rolling(window=period).sum()
        mfi = 100 - (100 / (1 + positive_flow / negative_flow))
        return mfi.values
    
    @staticmethod
    def _williams_r(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Williams %R."""
        high_max = data['high'].rolling(window=period).max()
        low_min = data['low'].rolling(window=period).min()
        williams_r = -100 * (high_max - data['close']) / (high_max - low_min)
        return williams_r.values
    
    # ========== INDICATEURS DE VOLATILITÉ ==========
    
    @staticmethod
    def _bollinger_bands(data: pd.DataFrame, period: int = 20, std: int = 2) -> Dict[str, np.ndarray]:
        """Bollinger Bands."""
        sma = data['close'].rolling(window=period).mean()
        rolling_std = data['close'].rolling(window=period).std()
        upper = sma + (rolling_std * std)
        lower = sma - (rolling_std * std)
        return {
            'upper': upper.values,
            'middle': sma.values,
            'lower': lower.values,
            'position': (data['close'] - lower) / (upper - lower).values
        }
    
    @staticmethod
    def _atr(data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """ATR (Average True Range)."""
        high = data['high']
        low = data['low']
        close = data['close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.values
    
    @staticmethod
    def _keltner_channels(data: pd.DataFrame, period: int = 20, atr_mult: int = 2) -> Dict[str, np.ndarray]:
        """Keltner Channels."""
        ema = data['close'].ewm(span=period, adjust=False).mean()
        atr = TechnicalIndicatorLibrary._atr(data, period)
        upper = ema + atr_mult * atr
        lower = ema - atr_mult * atr
        return {
            'upper': upper.values,
            'middle': ema.values,
            'lower': lower.values
        }
    
    @staticmethod
    def _donchian_channels(data: pd.DataFrame, period: int = 20) -> Dict[str, np.ndarray]:
        """Donchian Channels."""
        upper = data['high'].rolling(window=period).max()
        lower = data['low'].rolling(window=period).min()
        middle = (upper + lower) / 2
        return {
            'upper': upper.values,
            'middle': middle.values,
            'lower': lower.values
        }
    
    # ========== INDICATEURS DE VOLUME ==========
    
    @staticmethod
    def _obv(data: pd.DataFrame) -> np.ndarray:
        """OBV (On-Balance Volume)."""
        obv = np.zeros(len(data))
        obv[0] = data['volume'].iloc[0]
        for i in range(1, len(data)):
            if data['close'].iloc[i] > data['close'].iloc[i-1]:
                obv[i] = obv[i-1] + data['volume'].iloc[i]
            elif data['close'].iloc[i] < data['close'].iloc[i-1]:
                obv[i] = obv[i-1] - data['volume'].iloc[i]
            else:
                obv[i] = obv[i-1]
        return obv
    
    @staticmethod
    def _vwap(data: pd.DataFrame) -> np.ndarray:
        """VWAP (Volume Weighted Average Price)."""
        cumulative_tpv = (data['close'] * data['volume']).cumsum()
        cumulative_volume = data['volume'].cumsum()
        vwap = cumulative_tpv / cumulative_volume
        return vwap.values
    
    @staticmethod
    def _money_flow(data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Money Flow Indicators."""
        tp = (data['high'] + data['low'] + data['close']) / 3
        money_flow = tp * data['volume']
        positive_flow = money_flow.where(tp > tp.shift(), 0).cumsum()
        negative_flow = money_flow.where(tp < tp.shift(), 0).cumsum()
        net_flow = positive_flow - negative_flow
        ratio = positive_flow / negative_flow
        return {
            'positive_flow': positive_flow.values,
            'negative_flow': negative_flow.values,
            'net_flow': net_flow.values,
            'ratio': ratio.values
        }
    
    @staticmethod
    def _chaikin_oscillator(data: pd.DataFrame, fast: int = 3, slow: int = 10) -> np.ndarray:
        """Chaikin Oscillator."""
        mfm = ((data['close'] - data['low']) - (data['high'] - data['close'])) / (data['high'] - data['low'])
        mfv = mfm * data['volume']
        chaikin = mfv.ewm(span=fast, adjust=False).mean() - mfv.ewm(span=slow, adjust=False).mean()
        return chaikin.values


# ============== FACTORY ==============

class EnrichmentFactory:
    """Factory pour créer des composants d'enrichissement."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> EnrichmentEngine:
        """Crée un moteur d'enrichissement."""
        return EnrichmentEngine(
            data_manager=data_manager,
            config=config
        )
    
    @staticmethod
    def create_indicator_library() -> TechnicalIndicatorLibrary:
        """Crée une bibliothèque d'indicateurs."""
        return TechnicalIndicatorLibrary()


# ============== EXPORT ==============

__all__ = [
    "EnrichmentType",
    "IndicatorCategory",
    "FeatureType",
    "EnrichedData",
    "TechnicalIndicator",
    "FeatureSet",
    "EnrichmentEngineInterface",
    "EnrichmentEngine",
    "TechnicalIndicatorLibrary",
    "EnrichmentFactory"
]
