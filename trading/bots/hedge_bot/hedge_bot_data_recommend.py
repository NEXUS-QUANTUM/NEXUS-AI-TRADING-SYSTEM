# trading/bots/hedge_bot/hedge_bot_data_recommend.py

import asyncio
import logging
import time
import json
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque
from functools import reduce
import hashlib
import itertools

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.decomposition import NMF, TruncatedSVD
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.cluster import KMeans
    from sklearn.neighbors import NearestNeighbors
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import Ridge, Lasso, ElasticNet
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class RecommendationType(str, Enum):
    COLLABORATIVE = "collaborative"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    POPULARITY = "popularity"
    PERSONALIZED = "personalized"
    CONTEXTUAL = "contextual"
    SEQUENTIAL = "sequential"
    REINFORCEMENT = "reinforcement"
    ENSEMBLE = "ensemble"
    DEEP_LEARNING = "deep_learning"
    MATRIX_FACTORIZATION = "matrix_factorization"
    NEAREST_NEIGHBOR = "nearest_neighbor"
    BANDIT = "bandit"
    RULE_BASED = "rule_based"
    KNOWLEDGE_BASED = "knowledge_based"
    DEMOGRAPHIC = "demographic"
    TIME_BASED = "time_based"


class RecommendationScore(str, Enum):
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class RecommendationItem:
    id: str
    name: str
    category: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class RecommendationRequest:
    id: str
    user_id: str
    context: Dict[str, Any]
    limit: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    preferences: Dict[str, float] = field(default_factory=dict)
    exclude_ids: List[str] = field(default_factory=list)
    recommendation_type: Optional[RecommendationType] = None
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationResult:
    request_id: str
    items: List[RecommendationItem]
    total: int
    recommendation_type: RecommendationType
    confidence: float
    execution_time: float
    explanations: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    diversities: Dict[str, float] = field(default_factory=dict)


@dataclass
class UserProfile:
    id: str
    preferences: Dict[str, float]
    history: List[RecommendationItem]
    interactions: Dict[str, List[Dict]]
    embeddings: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ItemEmbedding:
    item_id: str
    embedding: np.ndarray
    version: str = "1.0.0"
    created_at: float = field(default_factory=time.time)


class RecommendationEngine:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._users: Dict[str, UserProfile] = {}
        self._items: Dict[str, RecommendationItem] = {}
        self._embeddings: Dict[str, ItemEmbedding] = {}
        self._requests: Dict[str, RecommendationRequest] = {}
        self._results: Dict[str, RecommendationResult] = {}
        self._recommenders: Dict[RecommendationType, Callable] = {}
        self._scorers: List[Callable] = []
        self._filters: List[Callable] = []
        self._diversity_measures: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_recommenders()
        self._initialize_default_data()

    def _initialize_recommenders(self) -> None:
        self.register_recommender(RecommendationType.COLLABORATIVE, self._recommend_collaborative)
        self.register_recommender(RecommendationType.CONTENT_BASED, self._recommend_content_based)
        self.register_recommender(RecommendationType.HYBRID, self._recommend_hybrid)
        self.register_recommender(RecommendationType.POPULARITY, self._recommend_popularity)
        self.register_recommender(RecommendationType.PERSONALIZED, self._recommend_personalized)
        self.register_recommender(RecommendationType.CONTEXTUAL, self._recommend_contextual)
        self.register_recommender(RecommendationType.SEQUENTIAL, self._recommend_sequential)
        self.register_recommender(RecommendationType.ENSEMBLE, self._recommend_ensemble)
        self.register_recommender(RecommendationType.MATRIX_FACTORIZATION, self._recommend_matrix_factorization)
        self.register_recommender(RecommendationType.NEAREST_NEIGHBOR, self._recommend_nearest_neighbor)
        self.register_recommender(RecommendationType.RULE_BASED, self._recommend_rule_based)
        self.register_recommender(RecommendationType.TIME_BASED, self._recommend_time_based)

    def _initialize_default_data(self) -> None:
        default_items = [
            RecommendationItem(
                id="item_1",
                name="BTC/USDT Long Strategy",
                category="strategy",
                attributes={"risk": "medium", "return": "high", "timeframe": "long"}
            ),
            RecommendationItem(
                id="item_2",
                name="ETH/USDT Scalping",
                category="strategy",
                attributes={"risk": "low", "return": "medium", "timeframe": "short"}
            ),
            RecommendationItem(
                id="item_3",
                name="Hedged Portfolio",
                category="portfolio",
                attributes={"risk": "low", "return": "medium", "timeframe": "medium"}
            ),
            RecommendationItem(
                id="item_4",
                name="Momentum Trading",
                category="strategy",
                attributes={"risk": "high", "return": "high", "timeframe": "medium"}
            ),
            RecommendationItem(
                id="item_5",
                name="Mean Reversion Strategy",
                category="strategy",
                attributes={"risk": "medium", "return": "medium", "timeframe": "medium"}
            ),
            RecommendationItem(
                id="item_6",
                name="Arbitrage Bot",
                category="bot",
                attributes={"risk": "low", "return": "low", "timeframe": "short"}
            ),
            RecommendationItem(
                id="item_7",
                name="AI Prediction Signal",
                category="signal",
                attributes={"risk": "medium", "return": "high", "timeframe": "short"}
            ),
            RecommendationItem(
                id="item_8",
                name="Risk Management Suite",
                category="tool",
                attributes={"risk": "low", "return": "medium", "timeframe": "long"}
            ),
            RecommendationItem(
                id="item_9",
                name="Options Trading Strategy",
                category="strategy",
                attributes={"risk": "high", "return": "high", "timeframe": "medium"}
            ),
            RecommendationItem(
                id="item_10",
                name="Market Making Bot",
                category="bot",
                attributes={"risk": "low", "return": "low", "timeframe": "short"}
            )
        ]
        
        for item in default_items:
            self._items[item.id] = item

    def register_recommender(self, rec_type: RecommendationType, recommender: Callable) -> None:
        self._recommenders[rec_type] = recommender

    def register_scorer(self, scorer: Callable) -> None:
        self._scorers.append(scorer)

    def register_filter(self, filter_func: Callable) -> None:
        self._filters.append(filter_func)

    def register_diversity_measure(self, measure: Callable) -> None:
        self._diversity_measures.append(measure)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_item(self, item: RecommendationItem) -> None:
        async with self._lock:
            self._items[item.id] = item
            await self._notify_observers("item_added", item)

    async def remove_item(self, item_id: str) -> bool:
        async with self._lock:
            if item_id in self._items:
                del self._items[item_id]
                await self._notify_observers("item_removed", item_id)
                return True
            return False

    async def update_user_profile(self, user_id: str, interactions: List[Dict]) -> None:
        async with self._lock:
            if user_id not in self._users:
                self._users[user_id] = UserProfile(
                    id=user_id,
                    preferences={},
                    history=[],
                    interactions=[]
                )
            
            user = self._users[user_id]
            user.interactions.extend(interactions)
            user.updated_at = time.time()
            
            await self._update_preferences(user)
            await self._notify_observers("user_updated", user)

    async def _update_preferences(self, user: UserProfile) -> None:
        if not user.interactions:
            return
        
        pref_counts = defaultdict(float)
        total = 0
        
        for interaction in user.interactions:
            item_id = interaction.get("item_id")
            weight = interaction.get("weight", 1.0)
            action_type = interaction.get("type", "view")
            
            if item_id in self._items:
                item = self._items[item_id]
                for attr, value in item.attributes.items():
                    pref_counts[f"{attr}_{value}"] += weight * 0.5
                
                if action_type == "purchase":
                    pref_counts[item.category] += weight * 2.0
                elif action_type == "like":
                    pref_counts[item.category] += weight * 1.5
                elif action_type == "view":
                    pref_counts[item.category] += weight * 0.5
                
                user.history.append(item)
                total += weight
        
        if total > 0:
            user.preferences = {k: v / total for k, v in pref_counts.items()}

    async def recommend(
        self,
        request: RecommendationRequest,
        rec_type: Optional[RecommendationType] = None,
        timeout: Optional[float] = None
    ) -> RecommendationResult:
        async with self._lock:
            start_time = time.time()
            rec_type = rec_type or request.recommendation_type or RecommendationType.HYBRID
            timeout = timeout or request.timeout
            
            self._requests[request.id] = request
            
            try:
                if rec_type not in self._recommenders:
                    raise ValueError(f"Recommender not found: {rec_type}")
                
                recommender = self._recommenders[rec_type]
                result = await asyncio.wait_for(
                    recommender(request),
                    timeout=timeout
                )
                
                if isinstance(result, list):
                    items = result
                    confidence = 0.5
                else:
                    items = result.get("items", [])
                    confidence = result.get("confidence", 0.5)
                
                items = await self._apply_filters(items, request)
                items = await self._apply_scorers(items, request)
                items = await self._apply_diversity(items, request)
                
                if request.limit and len(items) > request.limit:
                    items = items[:request.limit]
                
                total = len(items)
                diversities = {}
                
                for measure in self._diversity_measures:
                    try:
                        diversities[measure.__name__] = await measure(items)
                    except Exception as e:
                        logger.error(f"Diversity measure error: {e}")
                
                result_obj = RecommendationResult(
                    request_id=request.id,
                    items=items,
                    total=total,
                    recommendation_type=rec_type,
                    confidence=confidence,
                    execution_time=time.time() - start_time,
                    diversities=diversities,
                    metadata=request.metadata
                )
                
                self._results[request.id] = result_obj
                await self._notify_observers("recommendation_completed", result_obj)
                
                return result_obj
                
            except asyncio.TimeoutError:
                return RecommendationResult(
                    request_id=request.id,
                    items=[],
                    total=0,
                    recommendation_type=rec_type,
                    confidence=0.0,
                    execution_time=time.time() - start_time,
                    metadata={"timeout": True}
                )
            except Exception as e:
                logger.error(f"Recommendation error: {e}")
                return RecommendationResult(
                    request_id=request.id,
                    items=[],
                    total=0,
                    recommendation_type=rec_type,
                    confidence=0.0,
                    execution_time=time.time() - start_time,
                    metadata={"error": str(e)}
                )

    async def _recommend_collaborative(self, request: RecommendationRequest) -> List[RecommendationItem]:
        user_id = request.user_id
        
        if user_id not in self._users:
            return []
        
        user = self._users[user_id]
        user_items = set(item.id for item in user.history)
        
        similar_users = []
        for other_id, other_user in self._users.items():
            if other_id == user_id:
                continue
            
            other_items = set(item.id for item in other_user.history)
            intersection = user_items.intersection(other_items)
            
            if intersection:
                similarity = len(intersection) / max(len(user_items), len(other_items)) if user_items or other_items else 0
                if similarity > 0.1:
                    similar_users.append((other_user, similarity))
        
        similar_users.sort(key=lambda x: x[1], reverse=True)
        
        item_scores = defaultdict(float)
        for other_user, similarity in similar_users[:10]:
            for item in other_user.history:
                if item.id not in user_items:
                    item_scores[item.id] += similarity * 0.5
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason=f"Collaborative filtering from {len(similar_users)} similar users"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_content_based(self, request: RecommendationRequest) -> List[RecommendationItem]:
        user_id = request.user_id
        
        if user_id not in self._users:
            return []
        
        user = self._users[user_id]
        
        if not user.history:
            return []
        
        user_prefs = user.preferences
        item_scores = defaultdict(float)
        
        for item in self._items.values():
            if item.id in [h.id for h in user.history]:
                continue
            
            score = 0.0
            for attr, value in item.attributes.items():
                key = f"{attr}_{value}"
                score += user_prefs.get(key, 0.0)
            
            item_scores[item.id] = score
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason=f"Content-based matching on {len(user_prefs)} preferences"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_hybrid(self, request: RecommendationRequest) -> List[RecommendationItem]:
        collaborative = await self._recommend_collaborative(request)
        content_based = await self._recommend_content_based(request)
        
        combined_scores = defaultdict(float)
        items_map = {}
        
        for item in collaborative:
            combined_scores[item.id] += item.score * 0.6
            items_map[item.id] = item
        
        for item in content_based:
            combined_scores[item.id] += item.score * 0.4
            if item.id not in items_map:
                items_map[item.id] = item
        
        recommendations = []
        for item_id, score in sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in items_map:
                item = items_map[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason="Hybrid (collaborative + content-based)"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_popularity(self, request: RecommendationRequest) -> List[RecommendationItem]:
        item_scores = defaultdict(float)
        
        for user in self._users.values():
            for item in user.history:
                item_scores[item.id] += 1.0
        
        for item_id in item_scores:
            item_scores[item_id] /= len(self._users) if self._users else 1
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score * 2),
                    reason="Popularity based"
                )
                recommendations.append(rec_item)
        
        if len(recommendations) < request.limit:
            existing_ids = [r.id for r in recommendations]
            for item in self._items.values():
                if item.id not in existing_ids and len(recommendations) < request.limit:
                    rec_item = RecommendationItem(
                        id=item.id,
                        name=item.name,
                        category=item.category,
                        attributes=item.attributes,
                        score=0.0,
                        confidence=0.1,
                        reason="Fallback (popularity)"
                    )
                    recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_personalized(self, request: RecommendationRequest) -> List[RecommendationItem]:
        user_id = request.user_id
        
        if user_id not in self._users:
            return await self._recommend_popularity(request)
        
        user = self._users[user_id]
        user_prefs = user.preferences
        item_scores = defaultdict(float)
        
        for item in self._items.values():
            if item.id in [h.id for h in user.history]:
                continue
            
            score = 0.0
            for attr, value in item.attributes.items():
                key = f"{attr}_{value}"
                score += user_prefs.get(key, 0.0) * 0.7
            
            if item.category in user_prefs:
                score += user_prefs.get(item.category, 0.0) * 0.3
            
            item_scores[item.id] = score
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason="Personalized based on user history"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_contextual(self, request: RecommendationRequest) -> List[RecommendationItem]:
        context = request.context
        item_scores = defaultdict(float)
        
        for item in self._items.values():
            score = 0.0
            
            for key, value in context.items():
                if key in item.attributes:
                    if item.attributes[key] == value:
                        score += 1.0
            
            if score > 0:
                item_scores[item.id] = score / max(1, len(context))
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason=f"Contextual matching: {context}"
                )
                recommendations.append(rec_item)
        
        if len(recommendations) < request.limit:
            fallback = await self._recommend_popularity(request)
            for item in fallback:
                if item.id not in [r.id for r in recommendations]:
                    recommendations.append(item)
                    if len(recommendations) >= request.limit:
                        break
        
        return recommendations

    async def _recommend_sequential(self, request: RecommendationRequest) -> List[RecommendationItem]:
        user_id = request.user_id
        
        if user_id not in self._users:
            return await self._recommend_popularity(request)
        
        user = self._users[user_id]
        recent_items = user.history[-5:] if user.history else []
        
        if not recent_items:
            return await self._recommend_popularity(request)
        
        recent_categories = [item.category for item in recent_items]
        recent_attributes = []
        
        for item in recent_items:
            for attr, value in item.attributes.items():
                recent_attributes.append((attr, value))
        
        item_scores = defaultdict(float)
        
        for item in self._items.values():
            if item.id in [h.id for h in user.history]:
                continue
            
            score = 0.0
            
            if item.category in recent_categories:
                score += 0.5
            
            for attr, value in item.attributes.items():
                if (attr, value) in recent_attributes:
                    score += 0.3
            
            item_scores[item.id] = score
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason="Sequential recommendation based on recent items"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_ensemble(self, request: RecommendationRequest) -> List[RecommendationItem]:
        methods = [
            self._recommend_collaborative,
            self._recommend_content_based,
            self._recommend_popularity,
            self._recommend_personalized
        ]
        
        if request.context:
            methods.append(self._recommend_contextual)
        
        if request.user_id in self._users and self._users[request.user_id].history:
            methods.append(self._recommend_sequential)
        
        all_recommendations = []
        for method in methods:
            try:
                items = await method(request)
                all_recommendations.extend(items)
            except Exception as e:
                logger.error(f"Ensemble method error: {e}")
        
        combined_scores = defaultdict(float)
        item_map = {}
        
        for item in all_recommendations:
            combined_scores[item.id] += item.score
            if item.id not in item_map or item.confidence > item_map[item.id].confidence:
                item_map[item.id] = item
        
        recommendations = []
        for item_id, score in sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in item_map:
                item = item_map[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score / max(1, len(methods)),
                    confidence=min(1.0, item.confidence * 1.2),
                    reason="Ensemble of multiple recommendation methods"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_matrix_factorization(self, request: RecommendationRequest) -> List[RecommendationItem]:
        if not SKLEARN_AVAILABLE or not TORCH_AVAILABLE:
            return await self._recommend_popularity(request)
        
        user_id = request.user_id
        
        if user_id not in self._users:
            return await self._recommend_popularity(request)
        
        user_items = set(item.id for item in self._users[user_id].history)
        all_items = list(self._items.keys())
        
        user_factors = {}
        item_factors = {}
        
        for other_user in self._users.values():
            for item in other_user.history:
                if item.id not in item_factors:
                    item_factors[item.id] = np.random.randn(10)
        
        if not item_factors:
            return await self._recommend_popularity(request)
        
        user_factor = np.random.randn(10)
        
        item_scores = defaultdict(float)
        for item_id in all_items:
            if item_id in user_items:
                continue
            
            if item_id in item_factors:
                score = np.dot(user_factor, item_factors[item_id])
                item_scores[item_id] = float(score)
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                normalized_score = (score + 1) / 2
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=normalized_score,
                    confidence=min(1.0, normalized_score),
                    reason="Matrix factorization"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_nearest_neighbor(self, request: RecommendationRequest) -> List[RecommendationItem]:
        if not SKLEARN_AVAILABLE:
            return await self._recommend_popularity(request)
        
        user_id = request.user_id
        
        if user_id not in self._users:
            return await self._recommend_popularity(request)
        
        user = self._users[user_id]
        user_items = set(item.id for item in user.history)
        
        all_items = []
        for item in self._items.values():
            if item.id not in user_items:
                all_items.append(item)
        
        if not all_items:
            return []
        
        features = []
        item_ids = []
        
        for item in all_items:
            feature_vec = []
            for key, value in item.attributes.items():
                if isinstance(value, (int, float)):
                    feature_vec.append(float(value))
                else:
                    feature_vec.append(float(hash(value) % 100) / 100)
            features.append(feature_vec)
            item_ids.append(item.id)
        
        features = np.array(features)
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        n_neighbors = min(10, len(features_scaled))
        if n_neighbors < 2:
            return await self._recommend_popularity(request)
        
        nn = NearestNeighbors(n_neighbors=n_neighbors, metric='cosine')
        nn.fit(features_scaled)
        
        user_features = [0] * features_scaled.shape[1]
        for item in user.history:
            if item.id in self._items:
                item_features = []
                for key, value in self._items[item.id].attributes.items():
                    if isinstance(value, (int, float)):
                        item_features.append(float(value))
                    else:
                        item_features.append(float(hash(value) % 100) / 100)
                if item_features:
                    user_features = [(u + f) for u, f in zip(user_features, item_features)]
        
        if sum(abs(f) for f in user_features) == 0:
            return await self._recommend_popularity(request)
        
        distances, indices = nn.kneighbors([user_features])
        
        recommendations = []
        for idx in indices[0]:
            if idx < len(item_ids):
                item_id = item_ids[idx]
                if item_id in self._items:
                    item = self._items[item_id]
                    dist_idx = list(indices[0]).index(idx)
                    score = 1.0 / (1.0 + distances[0][dist_idx]) if dist_idx < len(distances[0]) else 0.5
                    rec_item = RecommendationItem(
                        id=item.id,
                        name=item.name,
                        category=item.category,
                        attributes=item.attributes,
                        score=score,
                        confidence=min(1.0, score),
                        reason=f"Nearest neighbor (k={n_neighbors})"
                    )
                    recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_rule_based(self, request: RecommendationRequest) -> List[RecommendationItem]:
        rules = request.constraints
        item_scores = defaultdict(float)
        
        for item in self._items.values():
            score = 0.0
            matched_rules = 0
            
            for rule in rules:
                if self._evaluate_rule(rule, item):
                    score += 1.0
                    matched_rules += 1
            
            if matched_rules > 0:
                item_scores[item.id] = score / max(1, len(rules))
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason=f"Rule-based: {len(rules)} rules matched"
                )
                recommendations.append(rec_item)
        
        return recommendations

    async def _recommend_time_based(self, request: RecommendationRequest) -> List[RecommendationItem]:
        now = time.time()
        time_weight = request.context.get("time_weight", 0.3)
        
        user_id = request.user_id
        if user_id in self._users:
            user = self._users[user_id]
            recent_items = user.history[-5:] if user.history else []
        else:
            recent_items = []
        
        item_scores = defaultdict(float)
        
        for item in self._items.values():
            score = 0.0
            
            if recent_items:
                for recent in recent_items:
                    if item.category == recent.category:
                        score += 0.5
                    for attr, value in item.attributes.items():
                        if attr in recent.attributes and recent.attributes[attr] == value:
                            score += 0.3
            
            time_factor = now - item.timestamp
            time_score = 1.0 / (1.0 + time_factor / (3600 * 24 * 30))
            score += time_score * time_weight
            
            item_scores[item.id] = score
        
        recommendations = []
        for item_id, score in sorted(item_scores.items(), key=lambda x: x[1], reverse=True)[:request.limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=score,
                    confidence=min(1.0, score),
                    reason="Time-based recommendation"
                )
                recommendations.append(rec_item)
        
        return recommendations

    def _evaluate_rule(self, rule: str, item: RecommendationItem) -> bool:
        try:
            if "==" in rule:
                key, value = rule.split("==")
                key = key.strip()
                value = value.strip()
                if key in item.attributes:
                    return str(item.attributes[key]) == value
            elif "!=" in rule:
                key, value = rule.split("!=")
                key = key.strip()
                value = value.strip()
                if key in item.attributes:
                    return str(item.attributes[key]) != value
            elif ">" in rule:
                key, value = rule.split(">")
                key = key.strip()
                value = float(value.strip())
                if key in item.attributes and isinstance(item.attributes[key], (int, float)):
                    return item.attributes[key] > value
            elif "<" in rule:
                key, value = rule.split("<")
                key = key.strip()
                value = float(value.strip())
                if key in item.attributes and isinstance(item.attributes[key], (int, float)):
                    return item.attributes[key] < value
            elif "contains" in rule:
                key, value = rule.split("contains")
                key = key.strip()
                value = value.strip()
                if key in item.attributes:
                    return value in str(item.attributes[key])
            elif "in" in rule:
                key, values = rule.split("in")
                key = key.strip()
                values = [v.strip() for v in values.split(",")]
                if key in item.attributes:
                    return str(item.attributes[key]) in values
        except Exception:
            pass
        
        return False

    async def _apply_filters(self, items: List[RecommendationItem], request: RecommendationRequest) -> List[RecommendationItem]:
        filtered = items
        
        if request.filters:
            for filter_func in self._filters:
                try:
                    filtered = await filter_func(filtered, request.filters)
                except Exception as e:
                    logger.error(f"Filter error: {e}")
        
        if request.exclude_ids:
            filtered = [item for item in filtered if item.id not in request.exclude_ids]
        
        return filtered

    async def _apply_scorers(self, items: List[RecommendationItem], request: RecommendationRequest) -> List[RecommendationItem]:
        for scorer in self._scorers:
            try:
                items = await scorer(items, request)
            except Exception as e:
                logger.error(f"Scorer error: {e}")
        
        return sorted(items, key=lambda x: x.score, reverse=True)

    async def _apply_diversity(self, items: List[RecommendationItem], request: RecommendationRequest) -> List[RecommendationItem]:
        if len(items) <= 1:
            return items
        
        diverse_items = []
        categories_seen = set()
        
        for item in items:
            if item.category not in categories_seen or len(categories_seen) >= len(set(i.category for i in items)):
                diverse_items.append(item)
                categories_seen.add(item.category)
            elif len(diverse_items) < len(items):
                diverse_items.append(item)
        
        return diverse_items

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        return self._users.get(user_id)

    async def get_item(self, item_id: str) -> Optional[RecommendationItem]:
        return self._items.get(item_id)

    async def get_recommendation_result(self, request_id: str) -> Optional[RecommendationResult]:
        return self._results.get(request_id)

    async def get_popular_items(self, limit: int = 10) -> List[RecommendationItem]:
        item_counts = defaultdict(int)
        
        for user in self._users.values():
            for item in user.history:
                item_counts[item.id] += 1
        
        result = []
        for item_id, count in sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:limit]:
            if item_id in self._items:
                item = self._items[item_id]
                rec_item = RecommendationItem(
                    id=item.id,
                    name=item.name,
                    category=item.category,
                    attributes=item.attributes,
                    score=count / max(1, len(self._users)),
                    confidence=min(1.0, count / max(1, len(self._users) * 2)),
                    reason="Popularity"
                )
                result.append(rec_item)
        
        return result

    async def get_similar_items(self, item_id: str, limit: int = 10) -> List[RecommendationItem]:
        if item_id not in self._items:
            return []
        
        target = self._items[item_id]
        similarities = []
        
        for item in self._items.values():
            if item.id == item_id:
                continue
            
            similarity = 0.0
            common_attrs = set(target.attributes.keys()) & set(item.attributes.keys())
            
            if common_attrs:
                for attr in common_attrs:
                    if target.attributes[attr] == item.attributes[attr]:
                        similarity += 1.0
                similarity /= len(common_attrs) if common_attrs else 1
            
            if target.category == item.category:
                similarity += 0.3
            
            similarities.append((item, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        result = []
        for item, similarity in similarities[:limit]:
            rec_item = RecommendationItem(
                id=item.id,
                name=item.name,
                category=item.category,
                attributes=item.attributes,
                score=similarity,
                confidence=min(1.0, similarity),
                reason=f"Similar to {target.name}"
            )
            result.append(rec_item)
        
        return result

    async def clear(self) -> None:
        async with self._lock:
            self._users.clear()
            self._items.clear()
            self._embeddings.clear()
            self._requests.clear()
            self._results.clear()
            self._initialize_default_data()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "users": len(self._users),
            "items": len(self._items),
            "embeddings": len(self._embeddings),
            "requests": len(self._requests),
            "results": len(self._results),
            "recommenders": len(self._recommenders),
            "scorers": len(self._scorers),
            "filters": len(self._filters),
            "diversity_measures": len(self._diversity_measures),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "RecommendationType",
    "RecommendationScore",
    "RecommendationItem",
    "RecommendationRequest",
    "RecommendationResult",
    "UserProfile",
    "ItemEmbedding",
    "RecommendationEngine"
]
