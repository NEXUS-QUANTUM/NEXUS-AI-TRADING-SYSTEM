"""
NEXUS AI TRADING SYSTEM - Sentiment Agent
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Sentiment Agent system with:
- Multi-source sentiment analysis (News, Social Media, Analyst Reports)
- Real-time sentiment scoring
- Natural Language Processing (NLP)
- Fine-tuned BERT models for financial sentiment
- Sentiment aggregation and weighting
- Market impact analysis
- Alert generation
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline,
    BertTokenizer,
    BertForSequenceClassification
)
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ai.agents.base_agent import BaseAgent, AgentHealth, AgentStatus
from ai.agents.agent_capabilities import AgentCapability
from ai.agents.agent_config import AgentConfig
from ai.agents.agent_registry import get_agent_registry
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import SentimentAnalysisError
from backend.services.news_service import NewsService
from backend.services.social_media_service import SocialMediaService
from backend.services.analyst_service import AnalystService

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class SentimentSource(str, Enum):
    """Sentiment sources"""
    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    ANALYST = "analyst"
    SOCIAL_MEDIA = "social_media"
    CRYPTO_PANIC = "crypto_panic"
    FEAR_GREED = "fear_greed"
    ON_CHAIN = "on_chain"
    MACRO = "macro"
    TECHNICAL = "technical"


class SentimentType(str, Enum):
    """Sentiment types"""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"
    FEAR = "fear"
    GREED = "greed"
    UNCERTAINTY = "uncertainty"


class SentimentModelType(str, Enum):
    """Sentiment model types"""
    FINBERT = "finbert"
    BERT = "bert"
    TEXTBLOB = "textblob"
    VADER = "vader"
    ROBERTA = "roberta"
    DISTILBERT = "distilbert"
    ALBERT = "albert"
    ENSEMBLE = "ensemble"


@dataclass
class SentimentItem:
    """Sentiment item"""
    id: str = field(default_factory=lambda: str(uuid4()))
    source: SentimentSource
    text: str
    timestamp: datetime
    sentiment_score: float  # -1 to 1
    sentiment_type: SentimentType
    confidence: float  # 0 to 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    relevance_score: float = 1.0  # 0 to 1
    impact_score: float = 0.0  # 0 to 1


@dataclass
class SentimentAggregation:
    """Aggregated sentiment"""
    symbol: str
    timestamp: datetime
    overall_score: float  # -1 to 1
    overall_type: SentimentType
    confidence: float  # 0 to 1
    sources: Dict[SentimentSource, float]  # source -> score
    scores: Dict[str, float]  # metric -> score
    volume: int  # number of items
    trend: float  # change in sentiment
    volatility: float  # sentiment volatility
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SentimentAlert:
    """Sentiment alert"""
    id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str
    timestamp: datetime
    alert_type: str  # 'threshold', 'change', 'divergence'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


class SentimentConfig(BaseModel):
    """Sentiment agent configuration"""
    enabled: bool = True
    symbols: List[str] = Field(default_factory=list)
    sources: List[SentimentSource] = Field(default_factory=list)
    models: List[SentimentModelType] = Field(default_factory=list)
    min_confidence: float = Field(default=0.6, ge=0, le=1)
    min_relevance: float = Field(default=0.5, ge=0, le=1)
    aggregation_method: str = Field(default="weighted_average")
    sentiment_threshold: float = Field(default=0.3, ge=0, le=1)
    alert_threshold: float = Field(default=0.5, ge=0, le=1)
    volatility_threshold: float = Field(default=0.3, ge=0, le=1)
    lookback_period: int = Field(default=100, gt=0)
    update_interval: int = Field(default=5, gt=0)
    model_refresh_interval: int = Field(default=3600, gt=0)
    cache_ttl: int = Field(default=3600, gt=0)
    max_items_per_source: int = Field(default=1000, gt=0)
    use_cache: bool = True
    enable_alerting: bool = True
    enable_impact_analysis: bool = True
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# SENTIMENT MODELS
# ========================================

class BaseSentimentModel:
    """Base sentiment model"""
    
    def __init__(self, config: SentimentConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the model"""
        raise NotImplementedError
    
    async def analyze(self, text: str) -> Tuple[float, float]:
        """
        Analyze sentiment of text.
        
        Returns:
            Tuple[float, float]: (sentiment_score, confidence)
        """
        raise NotImplementedError
    
    def get_model_type(self) -> SentimentModelType:
        """Get model type"""
        raise NotImplementedError


class FinBERTModel(BaseSentimentModel):
    """FinBERT model for financial sentiment analysis"""
    
    def __init__(self, config: SentimentConfig):
        super().__init__(config)
        self.model_name = "yiyanghkust/finbert-tone"
        self.tokenizer = None
        self.model = None
        self.pipeline = None
    
    async def initialize(self) -> None:
        """Initialize FinBERT model"""
        try:
            self.logger.info("Loading FinBERT model...")
            
            # Use tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.pipeline = pipeline(
                "sentiment-analysis",
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1  # CPU
            )
            
            self._initialized = True
            self.logger.info("FinBERT model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load FinBERT model: {e}")
            raise
    
    async def analyze(self, text: str) -> Tuple[float, float]:
        """Analyze sentiment using FinBERT"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Truncate long texts
            if len(text) > 512:
                text = text[:512]
            
            result = self.pipeline(text)[0]
            
            # Map labels to scores
            label = result['label']
            confidence = result['score']
            
            if label == 'Positive':
                score = 1.0
            elif label == 'Negative':
                score = -1.0
            else:
                score = 0.0
            
            return score, confidence
            
        except Exception as e:
            self.logger.error(f"FinBERT analysis error: {e}")
            return 0.0, 0.0
    
    def get_model_type(self) -> SentimentModelType:
        return SentimentModelType.FINBERT


class TextBlobModel(BaseSentimentModel):
    """TextBlob sentiment model"""
    
    async def initialize(self) -> None:
        """Initialize TextBlob model"""
        self._initialized = True
        self.logger.info("TextBlob model initialized")
    
    async def analyze(self, text: str) -> Tuple[float, float]:
        """Analyze sentiment using TextBlob"""
        try:
            blob = TextBlob(text)
            sentiment = blob.sentiment
            
            # Polarity: -1 to 1
            score = sentiment.polarity
            
            # Confidence based on subjectivity
            confidence = min(1.0, sentiment.subjectivity + 0.5)
            
            return score, confidence
            
        except Exception as e:
            self.logger.error(f"TextBlob analysis error: {e}")
            return 0.0, 0.0
    
    def get_model_type(self) -> SentimentModelType:
        return SentimentModelType.TEXTBLOB


class VADERModel(BaseSentimentModel):
    """VADER sentiment model"""
    
    def __init__(self, config: SentimentConfig):
        super().__init__(config)
        self.analyzer = None
    
    async def initialize(self) -> None:
        """Initialize VADER model"""
        self.analyzer = SentimentIntensityAnalyzer()
        self._initialized = True
        self.logger.info("VADER model initialized")
    
    async def analyze(self, text: str) -> Tuple[float, float]:
        """Analyze sentiment using VADER"""
        try:
            scores = self.analyzer.polarity_scores(text)
            
            # Compound score: -1 to 1
            score = scores['compound']
            
            # Confidence based on magnitude of sentiment
            confidence = min(1.0, abs(score) + 0.3)
            
            return score, confidence
            
        except Exception as e:
            self.logger.error(f"VADER analysis error: {e}")
            return 0.0, 0.0
    
    def get_model_type(self) -> SentimentModelType:
        return SentimentModelType.VADER


class EnsembleModel(BaseSentimentModel):
    """Ensemble sentiment model combining multiple models"""
    
    def __init__(self, config: SentimentConfig):
        super().__init__(config)
        self.models: Dict[SentimentModelType, BaseSentimentModel] = {}
    
    async def initialize(self) -> None:
        """Initialize ensemble model"""
        # Initialize component models
        model_classes = {
            SentimentModelType.FINBERT: FinBERTModel,
            SentimentModelType.TEXTBLOB: TextBlobModel,
            SentimentModelType.VADER: VADERModel
        }
        
        for model_type in self.config.models:
            if model_type in model_classes:
                model = model_classes[model_type](self.config)
                await model.initialize()
                self.models[model_type] = model
        
        self._initialized = True
        self.logger.info(f"Ensemble model initialized with {len(self.models)} models")
    
    async def analyze(self, text: str) -> Tuple[float, float]:
        """Analyze sentiment using ensemble"""
        if not self._initialized:
            await self.initialize()
        
        if not self.models:
            self.logger.warning("No models in ensemble")
            return 0.0, 0.0
        
        scores = []
        confidences = []
        
        for model in self.models.values():
            try:
                score, confidence = await model.analyze(text)
                if confidence > 0.3:  # Filter low confidence
                    scores.append(score)
                    confidences.append(confidence)
            except Exception as e:
                self.logger.error(f"Model {model.get_model_type()} error: {e}")
        
        if not scores:
            return 0.0, 0.0
        
        # Weighted average
        total_weight = sum(confidences)
        if total_weight == 0:
            return np.mean(scores), 0.5
        
        weighted_score = sum(s * c for s, c in zip(scores, confidences)) / total_weight
        avg_confidence = np.mean(confidences)
        
        return weighted_score, avg_confidence
    
    def get_model_type(self) -> SentimentModelType:
        return SentimentModelType.ENSEMBLE


# ========================================
# SENTIMENT AGENT
# ========================================

class SentimentAgent(BaseAgent):
    """
    Sentiment Agent for comprehensive sentiment analysis.
    
    Features:
    - Multi-source sentiment collection
    - Multiple sentiment models (FinBERT, VADER, TextBlob)
    - Real-time sentiment scoring
    - Sentiment aggregation
    - Market impact analysis
    - Alert generation
    - Trend analysis
    - Health monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._config = SentimentConfig(**config)
        self._model: Optional[BaseSentimentModel] = None
        
        # Services
        self._news_service = NewsService()
        self._social_service = SocialMediaService()
        self._analyst_service = AnalystService()
        
        # State
        self._sentiment_items: Dict[str, List[SentimentItem]] = {}
        self._aggregations: Dict[str, SentimentAggregation] = {}
        self._alerts: List[SentimentAlert] = []
        self._sentiment_history: Dict[str, List[Dict[str, Any]]] = {}
        self._last_update: Dict[str, datetime] = {}
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_items_processed": 0,
            "items_by_source": {},
            "alerts_generated": 0,
            "avg_confidence": 0.0,
            "avg_sentiment": 0.0,
            "models_used": [],
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        self._initialize_model()
        self._initialize_data_structures()
        
        self.logger.info("SentimentAgent initialized successfully")
    
    def _initialize_model(self) -> None:
        """Initialize sentiment model"""
        if SentimentModelType.ENSEMBLE in self._config.models:
            self._model = EnsembleModel(self._config)
        else:
            # Use first model in list
            model_type = self._config.models[0] if self._config.models else SentimentModelType.VADER
            model_classes = {
                SentimentModelType.FINBERT: FinBERTModel,
                SentimentModelType.TEXTBLOB: TextBlobModel,
                SentimentModelType.VADER: VADERModel
            }
            
            if model_type in model_classes:
                self._model = model_classes[model_type](self._config)
            else:
                self._model = VADERModel(self._config)
        
        self.logger.info(f"Initialized model: {self._model.get_model_type().value}")
    
    def _initialize_data_structures(self) -> None:
        """Initialize data structures"""
        for symbol in self._config.symbols:
            self._sentiment_items[symbol] = []
            self._sentiment_history[symbol] = []
            self._last_update[symbol] = datetime.utcnow()
    
    # ========================================
    # AGENT LIFECYCLE
    # ========================================
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the sentiment agent"""
        self.logger.info(f"Initializing SentimentAgent with config: {config}")
        
        if config:
            self._config = SentimentConfig(**{**self._config.dict(), **config})
        
        # Initialize model
        if self._model:
            await self._model.initialize()
        
        # Initialize services
        await self._news_service.initialize()
        await self._social_service.initialize()
        await self._analyst_service.initialize()
        
        self.capabilities = [
            AgentCapability.SENTIMENT_ANALYSIS,
            AgentCapability.NLP,
            AgentCapability.MARKET_INSIGHTS
        ]
        
        self.status = AgentStatus.INITIALIZED
        self.health = AgentHealth.HEALTHY
        self.logger.info("SentimentAgent initialized successfully")
    
    async def start(self) -> None:
        """Start the sentiment agent"""
        self.logger.info("Starting SentimentAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._sentiment_loop()))
        self._tasks.append(asyncio.create_task(self._aggregation_loop()))
        self._tasks.append(asyncio.create_task(self._alert_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.status = AgentStatus.RUNNING
        self.health = AgentHealth.HEALTHY
        self.logger.info("SentimentAgent started successfully")
    
    async def stop(self) -> None:
        """Stop the sentiment agent"""
        self.logger.info("Stopping SentimentAgent...")
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.status = AgentStatus.STOPPED
        self.logger.info("SentimentAgent stopped")
    
    async def pause(self) -> None:
        """Pause the sentiment agent"""
        self.logger.info("Pausing SentimentAgent...")
        self._running = False
        self.status = AgentStatus.PAUSED
        self.logger.info("SentimentAgent paused")
    
    async def resume(self) -> None:
        """Resume the sentiment agent"""
        self.logger.info("Resuming SentimentAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._sentiment_loop()))
        self._tasks.append(asyncio.create_task(self._aggregation_loop()))
        self._tasks.append(asyncio.create_task(self._alert_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.status = AgentStatus.RUNNING
        self.logger.info("SentimentAgent resumed")
    
    async def health_check(self) -> AgentHealth:
        """Check agent health"""
        try:
            if not self._running:
                return AgentHealth.DEGRADED
            
            if not self._model:
                return AgentHealth.UNHEALTHY
            
            # Check model availability
            try:
                await self._model.analyze("Test sentiment")
            except Exception as e:
                self.logger.error(f"Model health check failed: {e}")
                return AgentHealth.DEGRADED
            
            # Check data availability
            total_items = sum(len(items) for items in self._sentiment_items.values())
            if total_items == 0:
                return AgentHealth.DEGRADED
            
            return AgentHealth.HEALTHY
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return AgentHealth.UNHEALTHY
    
    # ========================================
    # SENTIMENT ANALYSIS
    # ========================================
    
    async def _sentiment_loop(self) -> None:
        """Main sentiment analysis loop"""
        while self._running:
            try:
                await self._collect_sentiment_data()
                await self._analyze_sentiment()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Sentiment loop error: {e}")
                self.health = AgentHealth.DEGRADED
            
            await asyncio.sleep(self._config.update_interval)
    
    async def _collect_sentiment_data(self) -> None:
        """Collect sentiment data from various sources"""
        for symbol in self._config.symbols:
            try:
                items = []
                
                # Collect from different sources
                for source in self._config.sources:
                    source_items = await self._collect_from_source(symbol, source)
                    items.extend(source_items)
                
                # Add to storage
                if items:
                    self._sentiment_items[symbol].extend(items)
                    
                    # Trim storage
                    if len(self._sentiment_items[symbol]) > self._config.max_items_per_source * len(self._config.sources):
                        self._sentiment_items[symbol] = self._sentiment_items[symbol][-self._config.max_items_per_source * len(self._config.sources):]
                    
                    self._last_update[symbol] = datetime.utcnow()
                    self._metrics["total_items_processed"] += len(items)
                    
                    # Update metrics by source
                    for item in items:
                        source_key = item.source.value
                        if source_key not in self._metrics["items_by_source"]:
                            self._metrics["items_by_source"][source_key] = 0
                        self._metrics["items_by_source"][source_key] += 1
                    
            except Exception as e:
                self.logger.error(f"Failed to collect data for {symbol}: {e}")
    
    async def _collect_from_source(
        self,
        symbol: str,
        source: SentimentSource
    ) -> List[SentimentItem]:
        """Collect sentiment data from a specific source"""
        items = []
        
        try:
            if source == SentimentSource.NEWS:
                news_items = await self._news_service.get_news(symbol)
                for item in news_items:
                    sentiment_item = SentimentItem(
                        source=SentimentSource.NEWS,
                        text=item['text'],
                        timestamp=item['timestamp'],
                        sentiment_score=0.0,
                        sentiment_type=SentimentType.NEUTRAL,
                        confidence=0.0,
                        metadata={
                            'title': item.get('title', ''),
                            'url': item.get('url', ''),
                            'source': item.get('source', '')
                        }
                    )
                    items.append(sentiment_item)
            
            elif source == SentimentSource.TWITTER:
                twitter_items = await self._social_service.get_tweets(symbol)
                for item in twitter_items:
                    sentiment_item = SentimentItem(
                        source=SentimentSource.TWITTER,
                        text=item['text'],
                        timestamp=item['timestamp'],
                        sentiment_score=0.0,
                        sentiment_type=SentimentType.NEUTRAL,
                        confidence=0.0,
                        metadata={
                            'user': item.get('user', ''),
                            'likes': item.get('likes', 0),
                            'retweets': item.get('retweets', 0)
                        }
                    )
                    items.append(sentiment_item)
            
            elif source == SentimentSource.REDDIT:
                reddit_items = await self._social_service.get_reddit_posts(symbol)
                for item in reddit_items:
                    sentiment_item = SentimentItem(
                        source=SentimentSource.REDDIT,
                        text=item['text'],
                        timestamp=item['timestamp'],
                        sentiment_score=0.0,
                        sentiment_type=SentimentType.NEUTRAL,
                        confidence=0.0,
                        metadata={
                            'title': item.get('title', ''),
                            'subreddit': item.get('subreddit', ''),
                            'upvotes': item.get('upvotes', 0)
                        }
                    )
                    items.append(sentiment_item)
            
            elif source == SentimentSource.ANALYST:
                analyst_items = await self._analyst_service.get_reports(symbol)
                for item in analyst_items:
                    sentiment_item = SentimentItem(
                        source=SentimentSource.ANALYST,
                        text=item['text'],
                        timestamp=item['timestamp'],
                        sentiment_score=0.0,
                        sentiment_type=SentimentType.NEUTRAL,
                        confidence=0.0,
                        metadata={
                            'analyst': item.get('analyst', ''),
                            'firm': item.get('firm', ''),
                            'rating': item.get('rating', '')
                        }
                    )
                    items.append(sentiment_item)
            
            # Add more sources as needed
            
        except Exception as e:
            self.logger.error(f"Failed to collect from {source.value}: {e}")
        
        return items
    
    async def _analyze_sentiment(self) -> None:
        """Analyze sentiment for collected items"""
        for symbol, items in self._sentiment_items.items():
            # Only analyze items without scores
            items_to_analyze = [
                item for item in items
                if item.sentiment_score == 0.0 and item.timestamp > datetime.utcnow() - timedelta(hours=24)
            ]
            
            if not items_to_analyze:
                continue
            
            for item in items_to_analyze:
                try:
                    # Check cache
                    cache_key = f"sentiment:{item.id}"
                    if self._config.use_cache and self.redis.exists(cache_key):
                        cached = self.redis.get(cache_key)
                        if cached:
                            data = json.loads(cached)
                            item.sentiment_score = data['score']
                            item.confidence = data['confidence']
                            self._metrics["cache_hits"] += 1
                            continue
                    
                    # Analyze with model
                    score, confidence = await self._model.analyze(item.text)
                    
                    # Apply filters
                    if confidence < self._config.min_confidence:
                        continue
                    
                    item.sentiment_score = score
                    item.confidence = confidence
                    item.sentiment_type = self._score_to_type(score)
                    
                    # Calculate relevance based on metadata
                    item.relevance_score = await self._calculate_relevance(item)
                    
                    # Store in cache
                    if self._config.use_cache:
                        self.redis.setex(
                            cache_key,
                            self._config.cache_ttl,
                            json.dumps({
                                'score': score,
                                'confidence': confidence
                            })
                        )
                        self._metrics["cache_misses"] += 1
                    
                except Exception as e:
                    self.logger.error(f"Failed to analyze item {item.id}: {e}")
    
    def _score_to_type(self, score: float) -> SentimentType:
        """Convert sentiment score to type"""
        if score >= 0.7:
            return SentimentType.VERY_BULLISH
        elif score >= 0.3:
            return SentimentType.BULLISH
        elif score >= -0.3:
            return SentimentType.NEUTRAL
        elif score >= -0.7:
            return SentimentType.BEARISH
        else:
            return SentimentType.VERY_BEARISH
    
    async def _calculate_relevance(self, item: SentimentItem) -> float:
        """Calculate relevance score for sentiment item"""
        # Base score
        relevance = 0.5
        
        # Boost for higher confidence
        relevance += item.confidence * 0.3
        
        # Boost for entities/topics
        if item.entities:
            relevance += min(0.2, len(item.entities) * 0.05)
        
        # Boost for source credibility
        source_weights = {
            SentimentSource.ANALYST: 0.3,
            SentimentSource.NEWS: 0.2,
            SentimentSource.SOCIAL_MEDIA: 0.1,
            SentimentSource.TWITTER: 0.1,
            SentimentSource.REDDIT: 0.05,
            SentimentSource.TELEGRAM: 0.05
        }
        relevance += source_weights.get(item.source, 0.1)
        
        return min(1.0, relevance)
    
    # ========================================
    # SENTIMENT AGGREGATION
    # ========================================
    
    async def _aggregation_loop(self) -> None:
        """Sentiment aggregation loop"""
        while self._running:
            try:
                await self._aggregate_sentiment()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Aggregation loop error: {e}")
            
            await asyncio.sleep(self._config.update_interval)
    
    async def _aggregate_sentiment(self) -> None:
        """Aggregate sentiment by symbol"""
        for symbol in self._sentiment_items.keys():
            try:
                # Get recent items
                recent_items = [
                    item for item in self._sentiment_items[symbol]
                    if item.timestamp > datetime.utcnow() - timedelta(hours=1)
                    and item.confidence >= self._config.min_confidence
                    and item.relevance_score >= self._config.min_relevance
                ]
                
                if not recent_items:
                    continue
                
                # Calculate weighted sentiment by source
                source_scores = {}
                source_weights = {
                    SentimentSource.ANALYST: 1.5,
                    SentimentSource.NEWS: 1.2,
                    SentimentSource.SOCIAL_MEDIA: 0.8,
                    SentimentSource.TWITTER: 0.7,
                    SentimentSource.REDDIT: 0.5,
                    SentimentSource.TELEGRAM: 0.5
                }
                
                total_weight = 0
                total_score = 0
                
                for source in self._config.sources:
                    source_items = [i for i in recent_items if i.source == source]
                    if not source_items:
                        continue
                    
                    # Average sentiment for source
                    avg_score = np.mean([i.sentiment_score for i in source_items])
                    avg_confidence = np.mean([i.confidence for i in source_items])
                    
                    weight = source_weights.get(source, 1.0) * avg_confidence
                    source_scores[source] = avg_score
                    
                    total_weight += weight
                    total_score += avg_score * weight
                
                # Overall sentiment
                overall_score = total_score / total_weight if total_weight > 0 else 0
                
                # Calculate confidence
                avg_confidence = np.mean([i.confidence for i in recent_items])
                
                # Calculate volatility
                scores = [i.sentiment_score for i in recent_items]
                volatility = np.std(scores) if len(scores) > 1 else 0
                
                # Calculate trend
                if len(scores) >= 10:
                    trend = (scores[-1] - scores[-10]) / 10
                else:
                    trend = 0
                
                # Calculate historical sentiment
                if symbol in self._sentiment_history:
                    self._sentiment_history[symbol].append({
                        'timestamp': datetime.utcnow().isoformat(),
                        'overall_score': overall_score,
                        'overall_type': self._score_to_type(overall_score).value,
                        'volatility': volatility,
                        'volume': len(recent_items)
                    })
                    
                    # Trim history
                    if len(self._sentiment_history[symbol]) > 1000:
                        self._sentiment_history[symbol] = self._sentiment_history[symbol][-1000:]
                
                # Create aggregation
                aggregation = SentimentAggregation(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    overall_score=overall_score,
                    overall_type=self._score_to_type(overall_score),
                    confidence=avg_confidence,
                    sources=source_scores,
                    scores={
                        'volatility': volatility,
                        'trend': trend,
                        'volume': len(recent_items),
                        'avg_confidence': avg_confidence
                    },
                    volume=len(recent_items),
                    trend=trend,
                    volatility=volatility,
                    metadata={
                        'sources_count': len(source_scores),
                        'total_items': len(recent_items)
                    }
                )
                
                self._aggregations[symbol] = aggregation
                
                # Update metrics
                self._metrics["avg_sentiment"] = (
                    self._metrics["avg_sentiment"] * 0.9 + overall_score * 0.1
                )
                self._metrics["avg_confidence"] = (
                    self._metrics["avg_confidence"] * 0.9 + avg_confidence * 0.1
                )
                
            except Exception as e:
                self.logger.error(f"Failed to aggregate sentiment for {symbol}: {e}")
    
    # ========================================
    # ALERT GENERATION
    # ========================================
    
    async def _alert_loop(self) -> None:
        """Alert generation loop"""
        while self._running:
            try:
                await self._generate_alerts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Alert loop error: {e}")
            
            await asyncio.sleep(10)
    
    async def _generate_alerts(self) -> None:
        """Generate sentiment alerts"""
        for symbol, aggregation in self._aggregations.items():
            if not aggregation:
                continue
            
            # Check threshold alerts
            if abs(aggregation.overall_score) >= self._config.alert_threshold:
                alert_type = "sentiment_threshold"
                severity = "high" if abs(aggregation.overall_score) >= 0.7 else "medium"
                message = f"{symbol} sentiment reached {aggregation.overall_score:.2f} ({aggregation.overall_type.value})"
                
                alert = SentimentAlert(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    data={
                        'sentiment_score': aggregation.overall_score,
                        'sentiment_type': aggregation.overall_type.value,
                        'confidence': aggregation.confidence,
                        'sources': {k.value: v for k, v in aggregation.sources.items()}
                    }
                )
                
                await self._handle_alert(alert)
            
            # Check volatility alerts
            if aggregation.volatility >= self._config.volatility_threshold:
                alert_type = "sentiment_volatility"
                severity = "medium"
                message = f"{symbol} sentiment volatility at {aggregation.volatility:.2f}"
                
                alert = SentimentAlert(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    data={
                        'volatility': aggregation.volatility,
                        'sentiment_score': aggregation.overall_score,
                        'volume': aggregation.volume
                    }
                )
                
                await self._handle_alert(alert)
            
            # Check rapid change alerts
            if len(self._sentiment_history.get(symbol, [])) >= 2:
                history = self._sentiment_history[symbol]
                current = history[-1]
                previous = history[-2]
                
                change = abs(current['overall_score'] - previous['overall_score'])
                if change >= 0.3:
                    alert_type = "sentiment_rapid_change"
                    severity = "high" if change >= 0.5 else "medium"
                    direction = "positive" if current['overall_score'] > previous['overall_score'] else "negative"
                    message = f"{symbol} sentiment rapidly changed {direction} by {change:.2f}"
                    
                    alert = SentimentAlert(
                        symbol=symbol,
                        timestamp=datetime.utcnow(),
                        alert_type=alert_type,
                        severity=severity,
                        message=message,
                        data={
                            'change': change,
                            'current_score': current['overall_score'],
                            'previous_score': previous['overall_score']
                        }
                    )
                    
                    await self._handle_alert(alert)
    
    async def _handle_alert(self, alert: SentimentAlert) -> None:
        """Handle sentiment alert"""
        self._alerts.append(alert)
        self._metrics["alerts_generated"] += 1
        
        # Log alert
        log_msg = f"Sentiment Alert [{alert.severity}]: {alert.message}"
        if alert.severity == "critical":
            self.logger.critical(log_msg)
        elif alert.severity == "high":
            self.logger.error(log_msg)
        elif alert.severity == "medium":
            self.logger.warning(log_msg)
        else:
            self.logger.info(log_msg)
        
        # Store in Redis
        try:
            key = f"sentiment_alert:{alert.id}"
            self.redis.setex(
                key,
                3600,
                json.dumps({
                    'symbol': alert.symbol,
                    'timestamp': alert.timestamp.isoformat(),
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'data': alert.data
                })
            )
        except Exception as e:
            self.logger.error(f"Failed to store alert: {e}")
        
        # Emit event for other agents
        self._emit_event("sentiment_alert", {
            'alert': alert.__dict__
        })
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                self.health = await self.health_check()
                self.logger.debug(f"Health: {self.health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self._config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_sentiment(
        self,
        symbol: str,
        source: Optional[SentimentSource] = None
    ) -> Optional[Dict[str, Any]]:
        """Get sentiment for symbol"""
        if symbol not in self._aggregations:
            return None
        
        aggregation = self._aggregations[symbol]
        
        result = {
            'symbol': symbol,
            'timestamp': aggregation.timestamp.isoformat(),
            'overall_score': aggregation.overall_score,
            'overall_type': aggregation.overall_type.value,
            'confidence': aggregation.confidence,
            'volume': aggregation.volume,
            'trend': aggregation.trend,
            'volatility': aggregation.volatility,
            'sources': {}
        }
        
        if source:
            if source in aggregation.sources:
                result['sources'][source.value] = aggregation.sources[source]
        else:
            result['sources'] = {k.value: v for k, v in aggregation.sources.items()}
        
        return result
    
    async def get_sentiment_history(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get sentiment history for symbol"""
        if symbol not in self._sentiment_history:
            return []
        
        return self._sentiment_history[symbol][-limit:]
    
    async def get_items(
        self,
        symbol: str,
        limit: int = 50,
        source: Optional[SentimentSource] = None
    ) -> List[Dict[str, Any]]:
        """Get sentiment items for symbol"""
        if symbol not in self._sentiment_items:
            return []
        
        items = self._sentiment_items[symbol]
        
        if source:
            items = [i for i in items if i.source == source]
        
        return [
            {
                'id': item.id,
                'source': item.source.value,
                'text': item.text[:200] + ('...' if len(item.text) > 200 else ''),
                'timestamp': item.timestamp.isoformat(),
                'sentiment_score': item.sentiment_score,
                'sentiment_type': item.sentiment_type.value,
                'confidence': item.confidence,
                'relevance_score': item.relevance_score
            }
            for item in items[-limit:]
        ]
    
    async def get_alerts(
        self,
        symbol: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get sentiment alerts"""
        alerts = self._alerts[-limit:]
        
        if symbol:
            alerts = [a for a in alerts if a.symbol == symbol]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return [
            {
                'id': alert.id,
                'symbol': alert.symbol,
                'timestamp': alert.timestamp.isoformat(),
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'data': alert.data
            }
            for alert in alerts
        ]
    
    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze a single text"""
        if not self._model:
            raise SentimentAnalysisError("Model not initialized")
        
        score, confidence = await self._model.analyze(text)
        sentiment_type = self._score_to_type(score)
        
        return {
            'text': text[:200] + ('...' if len(text) > 200 else ''),
            'sentiment_score': score,
            'sentiment_type': sentiment_type.value,
            'confidence': confidence
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return {
            **self._metrics,
            "models_used": self._metrics.get("models_used", []),
            "total_items": sum(len(items) for items in self._sentiment_items.values()),
            "active_symbols": len(self._aggregations),
            "alerts_count": len(self._alerts),
            "running": self._running,
            "status": self.status,
            "health": self.health
        }
    
    async def force_analysis(self, symbol: str) -> Dict[str, Any]:
        """Force sentiment analysis for symbol"""
        await self._collect_sentiment_data()
        await self._analyze_sentiment()
        await self._aggregate_sentiment()
        
        result = await self.get_sentiment(symbol)
        return result or {}
    
    # ========================================
    # STATE PERSISTENCE
    # ========================================
    
    async def save_state(self) -> None:
        """Save agent state"""
        try:
            state = {
                'sentiment_aggregations': {
                    symbol: {
                        'overall_score': agg.overall_score,
                        'overall_type': agg.overall_type.value,
                        'confidence': agg.confidence,
                        'timestamp': agg.timestamp.isoformat()
                    }
                    for symbol, agg in self._aggregations.items()
                },
                'metrics': self._metrics,
                'alerts': [
                    {
                        'id': alert.id,
                        'symbol': alert.symbol,
                        'timestamp': alert.timestamp.isoformat(),
                        'message': alert.message
                    }
                    for alert in self._alerts[-10:]
                ]
            }
            
            key = f"sentiment_agent_state:{self.agent_id}"
            self.redis.setex(
                key,
                settings.REDIS_AGENT_TTL,
                json.dumps(state, default=str)
            )
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")


# ========================================
# DEPENDENCY INJECTION
# ========================================

def create_sentiment_agent(config: Dict[str, Any]) -> SentimentAgent:
    """Create a sentiment agent instance"""
    return SentimentAgent(config)


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'SentimentAgent',
    'SentimentConfig',
    'SentimentSource',
    'SentimentType',
    'SentimentModelType',
    'SentimentItem',
    'SentimentAggregation',
    'SentimentAlert',
    'BaseSentimentModel',
    'FinBERTModel',
    'TextBlobModel',
    'VADERModel',
    'EnsembleModel',
    'create_sentiment_agent'
]
