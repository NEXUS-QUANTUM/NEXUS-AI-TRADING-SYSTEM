# trading/bots/hedge_bot/hedge_bot_data_perception.py
# Advanced Data Perception & Market Sentiment Analysis Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Perception Module - Module avancé de perception des données et d'analyse du sentiment
de marché pour le Hedge Bot. Analyse les perceptions du marché, le sentiment des investisseurs,
les tendances sociales, les indicateurs de peur et d'avidité, et l'impact des nouvelles.
"""

import asyncio
import json
import time
import re
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
import aiohttp
import aiohttp.client_exceptions
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_perception")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType
)


# ============== ENUMS & TYPES ==============

class SentimentSource(Enum):
    """Sources de sentiment."""
    TWITTER = "twitter"
    NEWS = "news"
    SOCIAL_MEDIA = "social_media"
    FORUMS = "forums"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    YOUTUBE = "youtube"
    WEBSITES = "websites"
    TRADING_VIEW = "trading_view"
    CUSTOM = "custom"


class SentimentType(Enum):
    """Types de sentiment."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    EXTREME_BULLISH = "extreme_bullish"
    EXTREME_BEARISH = "extreme_bearish"
    FEAR = "fear"
    GREED = "greed"
    UNCERTAINTY = "uncertainty"
    OPTIMISM = "optimism"
    PESSIMISM = "pessimism"


class PerceptionIndicator(Enum):
    """Indicateurs de perception."""
    FEAR_GREED_INDEX = "fear_greed_index"
    PUT_CALL_RATIO = "put_call_ratio"
    VIX = "vix"
    VOLUME_SENTIMENT = "volume_sentiment"
    SOCIAL_VOLUME = "social_volume"
    NEWS_SENTIMENT = "news_sentiment"
    WHALE_ACTIVITY = "whale_activity"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    LONG_SHORT_RATIO = "long_short_ratio"
    BULLISH_PERCENT = "bullish_percent"
    BEARISH_PERCENT = "bearish_percent"


# ============== DATA MODELS ==============

@dataclass
class SentimentData:
    """Données de sentiment."""
    sentiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    source: SentimentSource = SentimentSource.TWITTER
    sentiment_type: SentimentType = SentimentType.NEUTRAL
    score: float = 0.0
    confidence: float = 0.0
    volume: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    processed: bool = False


@dataclass
class PerceptionAggregate:
    """Agrégat de perception."""
    aggregate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    indicators: Dict[PerceptionIndicator, float] = field(default_factory=dict)
    overall_sentiment: SentimentType = SentimentType.NEUTRAL
    sentiment_score: float = 0.0
    fear_greed_score: float = 0.0
    bull_bear_ratio: float = 0.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class NewsArticle:
    """Article de presse."""
    article_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    source: str = ""
    url: str = ""
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sentiment: float = 0.0
    relevance: float = 0.0
    symbols: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SocialPost:
    """Publication sociale."""
    post_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    platform: str = ""
    author: str = ""
    content: str = ""
    sentiment: float = 0.0
    likes: int = 0
    shares: int = 0
    comments: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    symbols: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class PerceptionEngineInterface(ABC):
    """Interface abstraite pour le moteur de perception."""
    
    @abstractmethod
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyse le sentiment d'un texte."""
        pass
    
    @abstractmethod
    async def get_sentiment(self, symbol: str) -> SentimentData:
        """Récupère le sentiment pour un symbole."""
        pass
    
    @abstractmethod
    async def get_perception_aggregate(self, symbol: str) -> PerceptionAggregate:
        """Récupère l'agrégat de perception."""
        pass
    
    @abstractmethod
    async def process_news(self, article: NewsArticle) -> Dict[str, Any]:
        """Traite un article de presse."""
        pass


# ============== IMPLÉMENTATION ==============

class PerceptionEngine(PerceptionEngineInterface):
    """
    Moteur de perception avancé pour le Hedge Bot.
    Analyse le sentiment du marché et la perception des investisseurs.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion du sentiment
        self._sentiment_cache: Dict[str, SentimentData] = {}
        self._sentiment_lock = threading.RLock()
        
        # Gestion des agrégats
        self._aggregates: Dict[str, PerceptionAggregate] = {}
        self._agg_lock = threading.RLock()
        
        # Gestion des articles
        self._articles: List[NewsArticle] = []
        self._articles_lock = threading.RLock()
        
        # Gestion des posts sociaux
        self._posts: List[SocialPost] = []
        self._posts_lock = threading.RLock()
        
        # Analyseurs de sentiment
        self._vader_analyzer = SentimentIntensityAnalyzer()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "sentiment_analyses": 0,
            "articles_processed": 0,
            "posts_processed": 0,
            "aggregates_computed": 0,
            "avg_confidence": 0.0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PerceptionEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "fear_greed_threshold": 0.5,
            "sentiment_threshold": 0.2,
            "confidence_threshold": 0.5,
            "max_articles": 1000,
            "max_posts": 10000,
            "cache_size": 100,
            "cache_ttl": 3600,
            "enable_news_analysis": True,
            "enable_social_analysis": True,
            "enable_vader": True,
            "enable_textblob": True,
            "social_volume_window": 24,
            "news_impact_window": 72,
            "api_timeout": 30
        }
    
    async def start(self) -> None:
        """Démarre le moteur de perception."""
        logger.info("PerceptionEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config["api_timeout"])
        )
        
        # Chargement des données
        await self._load_data()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._social_monitor())
        asyncio.create_task(self._news_monitor())
        asyncio.create_task(self._aggregate_updater())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._cache_cleaner())
        
        logger.info("PerceptionEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de perception."""
        logger.info("PerceptionEngine stopping...")
        self._is_running = False
        
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("PerceptionEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyse le sentiment d'un texte."""
        self._stats["sentiment_analyses"] += 1
        
        try:
            # Analyse VADER
            if self.config["enable_vader"]:
                vader_scores = self._vader_analyzer.polarity_scores(text)
            else:
                vader_scores = {"compound": 0.0}
            
            # Analyse TextBlob
            if self.config["enable_textblob"]:
                blob = TextBlob(text)
                textblob_sentiment = blob.sentiment
            else:
                textblob_sentiment = (0.0, 0.0)
            
            # Agrégation
            compound_score = vader_scores["compound"]
            textblob_polarity = textblob_sentiment[0]
            
            # Score combiné
            combined_score = (compound_score + textblob_polarity) / 2
            
            # Classification
            sentiment_type = self._classify_sentiment(combined_score)
            
            # Métriques
            confidence = abs(combined_score)
            
            return {
                "sentiment": sentiment_type.value,
                "score": combined_score,
                "confidence": min(confidence, 1.0),
                "vader": vader_scores,
                "textblob": {
                    "polarity": textblob_sentiment[0],
                    "subjectivity": textblob_sentiment[1]
                }
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.0
            }
    
    async def get_sentiment(self, symbol: str) -> SentimentData:
        """Récupère le sentiment pour un symbole."""
        # Vérification du cache
        with self._sentiment_lock:
            if symbol in self._sentiment_cache:
                data = self._sentiment_cache[symbol]
                age = (datetime.now(timezone.utc) - data.timestamp).total_seconds()
                if age < self.config["cache_ttl"]:
                    return data
        
        # Collecte du sentiment
        sentiment_data = await self._collect_sentiment(symbol)
        
        with self._sentiment_lock:
            self._sentiment_cache[symbol] = sentiment_data
        
        return sentiment_data
    
    async def get_perception_aggregate(self, symbol: str) -> PerceptionAggregate:
        """Récupère l'agrégat de perception."""
        # Vérification du cache
        with self._agg_lock:
            if symbol in self._aggregates:
                agg = self._aggregates[symbol]
                age = (datetime.now(timezone.utc) - agg.timestamp).total_seconds()
                if age < self.config["cache_ttl"]:
                    return agg
        
        # Calcul de l'agrégat
        aggregate = await self._compute_aggregate(symbol)
        
        with self._agg_lock:
            self._aggregates[symbol] = aggregate
        
        return aggregate
    
    async def process_news(self, article: NewsArticle) -> Dict[str, Any]:
        """Traite un article de presse."""
        self._stats["articles_processed"] += 1
        
        # Analyse du sentiment
        sentiment = await self.analyze_sentiment(article.title + " " + article.content)
        article.sentiment = sentiment["score"]
        
        # Calcul de la pertinence
        article.relevance = await self._calculate_relevance(article)
        
        # Stockage
        with self._articles_lock:
            self._articles.append(article)
            
            # Limitation
            if len(self._articles) > self.config["max_articles"]:
                self._articles = self._articles[-self.config["max_articles"]:]
        
        # Mise à jour des symboles
        article.symbols = await self._extract_symbols(article.title + " " + article.content)
        
        return {
            "sentiment": sentiment["sentiment"],
            "score": sentiment["score"],
            "relevance": article.relevance,
            "symbols": article.symbols
        }
    
    # ========== MÉTHODES PRIVÉES - COLLECTE ==========
    
    async def _collect_sentiment(self, symbol: str) -> SentimentData:
        """Collecte le sentiment pour un symbole."""
        # Récupération des sources de sentiment
        sources = [
            await self._get_social_sentiment(symbol),
            await self._get_news_sentiment(symbol),
            await self._get_market_sentiment(symbol)
        ]
        
        # Agrégation
        scores = [s["score"] for s in sources if s is not None]
        confidences = [s["confidence"] for s in sources if s is not None]
        
        if not scores:
            return SentimentData(
                symbol=symbol,
                sentiment_type=SentimentType.NEUTRAL,
                score=0.0,
                confidence=0.0
            )
        
        # Score moyen pondéré
        avg_score = np.mean(scores)
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        # Classification
        sentiment_type = self._classify_sentiment(avg_score)
        
        return SentimentData(
            symbol=symbol,
            source=SentimentSource.CUSTOM,
            sentiment_type=sentiment_type,
            score=avg_score,
            confidence=avg_confidence
        )
    
    async def _get_social_sentiment(self, symbol: str) -> Optional[Dict[str, float]]:
        """Récupère le sentiment social."""
        # Dans un système réel, on interrogerait l'API Twitter, Reddit, etc.
        # Simulation
        return {
            "score": np.random.uniform(-1, 1),
            "confidence": np.random.uniform(0.5, 0.9)
        }
    
    async def _get_news_sentiment(self, symbol: str) -> Optional[Dict[str, float]]:
        """Récupère le sentiment des nouvelles."""
        # Simulation
        return {
            "score": np.random.uniform(-0.8, 0.8),
            "confidence": np.random.uniform(0.6, 0.95)
        }
    
    async def _get_market_sentiment(self, symbol: str) -> Optional[Dict[str, float]]:
        """Récupère le sentiment du marché."""
        # Simulation
        return {
            "score": np.random.uniform(-0.5, 0.5),
            "confidence": np.random.uniform(0.4, 0.8)
        }
    
    # ========== MÉTHODES PRIVÉES - AGRÉGATION ==========
    
    async def _compute_aggregate(self, symbol: str) -> PerceptionAggregate:
        """Calcule l'agrégat de perception."""
        # Récupération des données
        sentiment = await self.get_sentiment(symbol)
        
        # Indicateurs
        indicators = {
            PerceptionIndicator.SOCIAL_VOLUME: np.random.uniform(0, 1000),
            PerceptionIndicator.NEWS_SENTIMENT: sentiment.score,
            PerceptionIndicator.FEAR_GREED_INDEX: np.random.uniform(0, 100),
            PerceptionIndicator.BULLISH_PERCENT: np.random.uniform(0, 100),
            PerceptionIndicator.BEARISH_PERCENT: np.random.uniform(0, 100)
        }
        
        # Calcul du ratio bull/bear
        bull_bear_ratio = indicators[PerceptionIndicator.BULLISH_PERCENT] / (indicators[PerceptionIndicator.BEARISH_PERCENT] + 1)
        
        # Fear & Greed Score
        fear_greed_score = 50 + sentiment.score * 50
        
        # Sentiment global
        overall_sentiment = self._classify_sentiment(sentiment.score)
        
        return PerceptionAggregate(
            symbol=symbol,
            indicators=indicators,
            overall_sentiment=overall_sentiment,
            sentiment_score=sentiment.score,
            fear_greed_score=fear_greed_score,
            bull_bear_ratio=bull_bear_ratio,
            confidence=sentiment.confidence
        )
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _classify_sentiment(self, score: float) -> SentimentType:
        """Classifie le sentiment."""
        threshold = self.config["sentiment_threshold"]
        
        if score > threshold:
            return SentimentType.BULLISH
        elif score < -threshold:
            return SentimentType.BEARISH
        else:
            return SentimentType.NEUTRAL
    
    async def _calculate_relevance(self, article: NewsArticle) -> float:
        """Calcule la pertinence d'un article."""
        # Pertinence basée sur le contenu et les symboles
        relevance = 0.5
        
        # Ajustement par la longueur
        if len(article.content) > 500:
            relevance += 0.2
        
        # Ajustement par le sentiment
        if abs(article.sentiment) > 0.5:
            relevance += 0.2
        
        # Ajustement par les symboles
        if article.symbols:
            relevance += 0.1
        
        return min(1.0, relevance)
    
    async def _extract_symbols(self, text: str) -> List[str]:
        """Extrait les symboles d'un texte."""
        # Simulation d'extraction de symboles
        pattern = r'\b[A-Z]{2,5}\b'
        symbols = re.findall(pattern, text)
        return list(set(symbols))[:5]
    
    # ========== MÉTHODES PRIVÉES - MONITORING ==========
    
    async def _social_monitor(self) -> None:
        """Monitor les réseaux sociaux."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Récupération des posts sociaux
                # Dans un système réel, on interrogerait les API sociales
                pass
                
            except Exception as e:
                logger.error(f"Social monitor error: {e}")
    
    async def _news_monitor(self) -> None:
        """Monitor les nouvelles."""
        while self._is_running:
            await asyncio.sleep(600)  # 10 minutes
            
            try:
                # Récupération des articles de presse
                # Dans un système réel, on interrogerait les APIs de news
                pass
                
            except Exception as e:
                logger.error(f"News monitor error: {e}")
    
    async def _aggregate_updater(self) -> None:
        """Met à jour les agrégats."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Mise à jour des agrégats pour les symboles actifs
                symbols = ["BTC-USD", "ETH-USD", "AAPL", "SPX"]
                
                for symbol in symbols:
                    await self.get_perception_aggregate(symbol)
                
                self._stats["aggregates_computed"] += len(symbols)
                
            except Exception as e:
                logger.error(f"Aggregate updater error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._sentiment_lock:
                    if len(self._sentiment_cache) > self.config["cache_size"]:
                        keys = list(self._sentiment_cache.keys())
                        for key in keys[:len(self._sentiment_cache) - self.config["cache_size"]]:
                            del self._sentiment_cache[key]
                
                with self._agg_lock:
                    if len(self._aggregates) > self.config["cache_size"]:
                        keys = list(self._aggregates.keys())
                        for key in keys[:len(self._aggregates) - self.config["cache_size"]]:
                            del self._aggregates[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._sentiment_lock:
                    self._stats["cached_sentiment"] = len(self._sentiment_cache)
                with self._agg_lock:
                    self._stats["cached_aggregates"] = len(self._aggregates)
                with self._articles_lock:
                    self._stats["cached_articles"] = len(self._articles)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "perception:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_data(self) -> None:
        """Charge les données existantes."""
        try:
            if self.data_manager:
                # Chargement du sentiment
                sentiment_data = await self.data_manager.retrieve(
                    "perception:sentiment",
                    DataType.SENTIMENT
                )
                
                if sentiment_data:
                    for s_dict in sentiment_data:
                        sentiment = self._deserialize_sentiment(s_dict)
                        if sentiment:
                            with self._sentiment_lock:
                                self._sentiment_cache[sentiment.symbol] = sentiment
                
                # Chargement des agrégats
                agg_data = await self.data_manager.retrieve(
                    "perception:aggregates",
                    DataType.AGGREGATE
                )
                
                if agg_data:
                    for a_dict in agg_data:
                        aggregate = self._deserialize_aggregate(a_dict)
                        if aggregate:
                            with self._agg_lock:
                                self._aggregates[aggregate.symbol] = aggregate
            
            logger.info(f"Loaded {len(self._sentiment_cache)} sentiment records")
            
        except Exception as e:
            logger.error(f"Load data error: {e}")
    
    def _deserialize_sentiment(self, data: Dict) -> Optional[SentimentData]:
        """Désérialise des données de sentiment."""
        try:
            return SentimentData(
                sentiment_id=data.get("sentiment_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                source=SentimentSource(data.get("source", "twitter")),
                sentiment_type=SentimentType(data.get("sentiment_type", "neutral")),
                score=data.get("score", 0.0),
                confidence=data.get("confidence", 0.0),
                volume=data.get("volume", 0),
                positive_count=data.get("positive_count", 0),
                negative_count=data.get("negative_count", 0),
                neutral_count=data.get("neutral_count", 0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                text=data.get("text", ""),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                processed=data.get("processed", False)
            )
        except Exception as e:
            logger.error(f"Error deserializing sentiment: {e}")
            return None
    
    def _deserialize_aggregate(self, data: Dict) -> Optional[PerceptionAggregate]:
        """Désérialise un agrégat."""
        try:
            return PerceptionAggregate(
                aggregate_id=data.get("aggregate_id", str(uuid.uuid4())),
                symbol=data.get("symbol", ""),
                indicators={PerceptionIndicator(k): v for k, v in data.get("indicators", {}).items()},
                overall_sentiment=SentimentType(data.get("overall_sentiment", "neutral")),
                sentiment_score=data.get("sentiment_score", 0.0),
                fear_greed_score=data.get("fear_greed_score", 0.0),
                bull_bear_ratio=data.get("bull_bear_ratio", 0.0),
                confidence=data.get("confidence", 0.0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing aggregate: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_fear_greed_index(self) -> Dict[str, float]:
        """Récupère l'indice de peur et d'avidité."""
        # Simulation de l'indice
        return {
            "score": np.random.uniform(0, 100),
            "level": "neutral",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_whale_activity(self, symbol: str) -> Dict[str, Any]:
        """Récupère l'activité des whales."""
        # Simulation
        return {
            "symbol": symbol,
            "large_trades": np.random.randint(0, 10),
            "whale_count": np.random.randint(0, 5),
            "volume": np.random.uniform(100000, 10000000),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._sentiment_lock:
            self._stats["sentiment_count"] = len(self._sentiment_cache)
        with self._agg_lock:
            self._stats["aggregate_count"] = len(self._aggregates)
        
        return self._stats.copy()


# ============== SENTIMENT VISUALIZER ==============

class SentimentVisualizer:
    """
    Visualiseur de sentiment.
    Génère des visualisations pour l'analyse de sentiment.
    """
    
    def __init__(self, engine: PerceptionEngine):
        self.engine = engine
    
    async def plot_sentiment_timeline(self, symbol: str, days: int = 30) -> str:
        """Génère un graphique de l'évolution du sentiment."""
        import matplotlib.pyplot as plt
        
        # Récupération des données
        sentiment = await self.engine.get_sentiment(symbol)
        
        # Simulation de timeline
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=days)
        scores = np.cumsum(np.random.normal(0, 0.1, days))
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dates, scores, color='blue', linewidth=2)
        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
        ax.fill_between(dates, 0, scores, where=(scores > 0), color='green', alpha=0.3)
        ax.fill_between(dates, 0, scores, where=(scores < 0), color='red', alpha=0.3)
        
        ax.set_title(f'Sentiment Timeline - {symbol}')
        ax.set_xlabel('Date')
        ax.set_ylabel('Sentiment Score')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        path = f"sentiment_{symbol}_{int(time.time())}.png"
        plt.savefig(path, dpi=100)
        plt.close()
        
        return path


# ============== FACTORY ==============

class PerceptionFactory:
    """Factory pour créer des composants de perception."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PerceptionEngine:
        """Crée un moteur de perception."""
        engine = PerceptionEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_visualizer(engine: PerceptionEngine) -> SentimentVisualizer:
        """Crée un visualiseur de sentiment."""
        return SentimentVisualizer(engine)


# ============== EXPORT ==============

__all__ = [
    "SentimentSource",
    "SentimentType",
    "PerceptionIndicator",
    "SentimentData",
    "PerceptionAggregate",
    "NewsArticle",
    "SocialPost",
    "PerceptionEngineInterface",
    "PerceptionEngine",
    "SentimentVisualizer",
    "PerceptionFactory"
]
