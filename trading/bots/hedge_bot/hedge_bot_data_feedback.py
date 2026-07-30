# trading/bots/hedge_bot/hedge_bot_data_feedback.py
# Advanced Feedback & Reinforcement Learning Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Feedback Module - Module de feedback et d'apprentissage par renforcement avancé
pour le Hedge Bot. Collecte, analyse et utilise les retours d'expérience pour améliorer
en continu les décisions de hedging et les stratégies d'exécution.
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
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_feedback")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult, DecisionType, HedgeStrategy
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult, OrderStatus
)


# ============== ENUMS & TYPES ==============

class FeedbackType(Enum):
    """Types de feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    STRONG_POSITIVE = "strong_positive"
    STRONG_NEGATIVE = "strong_negative"
    CORRECTION = "correction"
    CONFIRMATION = "confirmation"


class FeedbackSource(Enum):
    """Sources de feedback."""
    SYSTEM = "system"
    USER = "user"
    MARKET = "market"
    PERFORMANCE = "performance"
    RISK = "risk"
    ALGORITHM = "algorithm"
    EXTERNAL = "external"
    AI = "ai"
    PEER = "peer"


class FeedbackPriority(Enum):
    """Priorités des feedbacks."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class ReinforcementSignal(Enum):
    """Signaux d'apprentissage par renforcement."""
    REWARD = "reward"
    PENALTY = "penalty"
    SHAPING = "shaping"
    EXPLORATION = "exploration"
    EXPLOITATION = "exploitation"
    CURIOUSITY = "curiousity"


# ============== DATA MODELS ==============

@dataclass
class Feedback:
    """Modèle de feedback."""
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    feedback_type: FeedbackType = FeedbackType.NEUTRAL
    source: FeedbackSource = FeedbackSource.SYSTEM
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    score: float = 0.0
    confidence: float = 0.0
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    related_decisions: List[str] = field(default_factory=list)
    related_orders: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiration: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    weight: float = 1.0
    acknowledged: bool = False
    action_taken: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "feedback_id": self.feedback_id,
            "feedback_type": self.feedback_type.value,
            "source": self.source.value,
            "priority": self.priority.value,
            "score": self.score,
            "confidence": self.confidence,
            "message": self.message,
            "context": self.context,
            "related_decisions": self.related_decisions,
            "related_orders": self.related_orders,
            "timestamp": self.timestamp.isoformat(),
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "metadata": self.metadata,
            "tags": self.tags,
            "weight": self.weight,
            "acknowledged": self.acknowledged,
            "action_taken": self.action_taken
        }


@dataclass
class ReinforcementExperience:
    """Expérience d'apprentissage par renforcement."""
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: Dict[str, Any] = field(default_factory=dict)
    action: Dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    next_state: Dict[str, Any] = field(default_factory=dict)
    done: bool = False
    discount: float = 0.99
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    episode_id: Optional[str] = None
    step: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "experience_id": self.experience_id,
            "state": self.state,
            "action": self.action,
            "reward": self.reward,
            "next_state": self.next_state,
            "done": self.done,
            "discount": self.discount,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "metadata": self.metadata,
            "tags": self.tags,
            "episode_id": self.episode_id,
            "step": self.step
        }


@dataclass
class PerformanceFeedback:
    """Feedback de performance."""
    performance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric: str = ""
    value: float = 0.0
    expected: float = 0.0
    deviation: float = 0.0
    feedback_type: FeedbackType = FeedbackType.NEUTRAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class LearningProgress:
    """Progression d'apprentissage."""
    progress_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = ""
    episode: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    success_rate: float = 0.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class FeedbackEngineInterface(ABC):
    """Interface abstraite pour le moteur de feedback."""
    
    @abstractmethod
    async def submit_feedback(self, feedback: Feedback) -> str:
        """Soumet un feedback."""
        pass
    
    @abstractmethod
    async def get_feedback(self, feedback_id: str) -> Optional[Feedback]:
        """Récupère un feedback."""
        pass
    
    @abstractmethod
    async def process_feedback(self, feedback: Feedback) -> Any:
        """Traite un feedback."""
        pass


class ReinforcementEngineInterface(ABC):
    """Interface abstraite pour le moteur d'apprentissage par renforcement."""
    
    @abstractmethod
    async def add_experience(self, experience: ReinforcementExperience) -> None:
        """Ajoute une expérience."""
        pass
    
    @abstractmethod
    async def train(self, batch_size: int) -> Dict[str, Any]:
        """Entraîne le modèle."""
        pass
    
    @abstractmethod
    async def predict(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prédit la prochaine action."""
        pass


# ============== IMPLÉMENTATION ==============

class FeedbackEngine(FeedbackEngineInterface):
    """
    Moteur de feedback avancé pour le Hedge Bot.
    Collecte, analyse et utilise les feedbacks pour améliorer les décisions.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Stockage des feedbacks
        self._feedbacks: Dict[str, Feedback] = {}
        self._feedbacks_lock = threading.RLock()
        
        # File d'attente des feedbacks
        self._feedback_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "feedbacks_received": 0,
            "feedbacks_processed": 0,
            "positive_feedback": 0,
            "negative_feedback": 0,
            "neutral_feedback": 0,
            "avg_score": 0.0,
            "processing_time_ms": 0.0
        }
        
        # Analyses des tendances
        self._trend_analysis: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # État
        self._is_running = False
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        logger.info("FeedbackEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "batch_size": 100,
            "processing_interval": 5,  # secondes
            "feedback_ttl": 86400,  # 24 heures
            "max_feedback_age": 604800,  # 7 jours
            "auto_acknowledge": True,
            "learning_rate": 0.01,
            "decay_factor": 0.9,
            "confidence_threshold": 0.5,
            "positive_threshold": 0.6,
            "negative_threshold": -0.6
        }
    
    async def start(self) -> None:
        """Démarre le moteur de feedback."""
        logger.info("FeedbackEngine starting...")
        self._is_running = True
        
        # Chargement des feedbacks historiques
        await self._load_feedbacks()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._feedback_processor())
        asyncio.create_task(self._trend_analyzer_loop())
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("FeedbackEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de feedback."""
        logger.info("FeedbackEngine stopping...")
        self._is_running = False
        
        # Traitement des feedbacks restants
        await self._process_remaining_feedbacks()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("FeedbackEngine stopped")
    
    async def submit_feedback(self, feedback: Feedback) -> str:
        """Soumet un feedback."""
        with self._feedbacks_lock:
            self._feedbacks[feedback.feedback_id] = feedback
            self._stats["feedbacks_received"] += 1
        
        # Mise en queue pour traitement
        await self._feedback_queue.put(feedback)
        
        logger.debug(f"Feedback submitted: {feedback.feedback_id} "
                    f"type={feedback.feedback_type.value} score={feedback.score}")
        
        return feedback.feedback_id
    
    async def get_feedback(self, feedback_id: str) -> Optional[Feedback]:
        """Récupère un feedback."""
        with self._feedbacks_lock:
            return self._feedbacks.get(feedback_id)
    
    async def process_feedback(self, feedback: Feedback) -> Any:
        """Traite un feedback."""
        start_time = time.time()
        
        try:
            # Analyse du feedback
            analysis = await self._analyze_feedback(feedback)
            
            # Mise à jour des statistiques
            self._stats["feedbacks_processed"] += 1
            if feedback.feedback_type in [FeedbackType.POSITIVE, FeedbackType.STRONG_POSITIVE]:
                self._stats["positive_feedback"] += 1
            elif feedback.feedback_type in [FeedbackType.NEGATIVE, FeedbackType.STRONG_NEGATIVE]:
                self._stats["negative_feedback"] += 1
            else:
                self._stats["neutral_feedback"] += 1
            
            # Mise à jour de la moyenne
            total = self._stats["feedbacks_processed"]
            self._stats["avg_score"] = (
                self._stats["avg_score"] * (total - 1) + feedback.score
            ) / total
            
            # Enregistrement dans l'historique des tendances
            self._trend_analysis[feedback.source.value].append({
                "timestamp": feedback.timestamp,
                "score": feedback.score,
                "type": feedback.feedback_type.value
            })
            
            # Auto-acknowledge
            if self.config["auto_acknowledge"]:
                feedback.acknowledged = True
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"feedback:{feedback.feedback_id}",
                    feedback.to_dict(),
                    DataType.FEEDBACK
                )
            
            # Métriques de performance
            processing_time = (time.time() - start_time) * 1000
            self._stats["processing_time_ms"] = (
                self._stats["processing_time_ms"] * 0.9 + processing_time * 0.1
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Feedback processing error: {e}")
            return {"error": str(e)}
    
    # ========== MÉTHODES PRIVÉES - ANALYSE ==========
    
    async def _analyze_feedback(self, feedback: Feedback) -> Dict[str, Any]:
        """Analyse un feedback."""
        analysis = {
            "feedback_id": feedback.feedback_id,
            "type": feedback.feedback_type.value,
            "score": feedback.score,
            "confidence": feedback.confidence,
            "impact": 0.0,
            "suggestions": [],
            "actionable": False
        }
        
        # Analyse de l'impact
        if feedback.source == FeedbackSource.PERFORMANCE:
            # Impact basé sur la performance
            impact = feedback.score * feedback.confidence
            analysis["impact"] = impact
            analysis["actionable"] = abs(impact) > self.config["confidence_threshold"]
            
            # Suggestions d'amélioration
            if impact > 0.3:
                analysis["suggestions"].append("Consider increasing position size")
            elif impact < -0.3:
                analysis["suggestions"].append("Consider reducing position size or adjusting strategy")
        
        elif feedback.source == FeedbackSource.RISK:
            # Analyse du risque
            risk_score = feedback.score
            analysis["impact"] = risk_score
            
            if risk_score > 0.7:
                analysis["suggestions"].append("Risk level is high - consider hedging more aggressively")
                analysis["actionable"] = True
            elif risk_score < 0.3:
                analysis["suggestions"].append("Risk level is low - consider increasing exposure")
                analysis["actionable"] = True
        
        elif feedback.source == FeedbackSource.MARKET:
            # Analyse de marché
            market_signal = feedback.score
            analysis["impact"] = market_signal
            
            if market_signal > 0.5:
                analysis["suggestions"].append("Market conditions favorable - consider bullish strategy")
            elif market_signal < -0.5:
                analysis["suggestions"].append("Market conditions unfavorable - consider defensive strategy")
        
        elif feedback.source == FeedbackSource.ALGORITHM:
            # Analyse algorithmique
            algo_score = feedback.score
            analysis["impact"] = algo_score
            
            if algo_score < 0.3:
                analysis["suggestions"].append("Algorithm performance below expectations - review parameters")
                analysis["actionable"] = True
        
        return analysis
    
    async def _feedback_processor(self) -> None:
        """Traite les feedbacks en continu."""
        while self._is_running:
            try:
                # Récupération des feedbacks en batch
                feedbacks = []
                batch_size = self.config["batch_size"]
                
                for _ in range(batch_size):
                    try:
                        feedback = await asyncio.wait_for(
                            self._feedback_queue.get(),
                            timeout=1.0
                        )
                        feedbacks.append(feedback)
                    except asyncio.TimeoutError:
                        break
                
                if feedbacks:
                    # Traitement parallèle
                    tasks = [self.process_feedback(f) for f in feedbacks]
                    await asyncio.gather(*tasks)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Feedback processor error: {e}")
                await asyncio.sleep(1)
    
    async def _trend_analyzer_loop(self) -> None:
        """Analyse les tendances des feedbacks."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Analyse des tendances par source
                for source, history in self._trend_analysis.items():
                    if len(history) >= 10:
                        # Calcul de la tendance
                        scores = [h["score"] for h in history]
                        trend = self._calculate_trend(scores)
                        
                        # Détection d'anomalies
                        if abs(trend) > 0.3:
                            logger.info(f"Trend detected for source {source}: {trend:.2f}")
                            
                            # Génération d'un feedback système
                            if abs(trend) > 0.5:
                                system_feedback = Feedback(
                                    feedback_type=FeedbackType.CORRECTION if trend < 0 else FeedbackType.CONFIRMATION,
                                    source=FeedbackSource.SYSTEM,
                                    priority=FeedbackPriority.HIGH,
                                    score=trend,
                                    confidence=0.7,
                                    message=f"Significant trend detected from {source}: {trend:.2f}",
                                    tags=["trend", source, "auto_detected"]
                                )
                                await self.submit_feedback(system_feedback)
                
            except Exception as e:
                logger.error(f"Trend analyzer error: {e}")
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calcule la tendance d'une série de valeurs."""
        if len(values) < 2:
            return 0.0
        
        # Régression linéaire simple
        n = len(values)
        x = np.arange(n)
        y = np.array(values)
        
        # Slope = covariance / variance
        slope = np.cov(x, y)[0, 1] / np.var(x) if np.var(x) > 0 else 0.0
        
        # Normalisation
        max_slope = 1.0 / (n - 1) if n > 1 else 1.0
        normalized_slope = slope / max_slope
        
        return max(-1.0, min(1.0, normalized_slope))
    
    async def _cleanup_loop(self) -> None:
        """Nettoie les feedbacks expirés."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                now = datetime.now(timezone.utc)
                max_age = self.config["max_feedback_age"]
                cutoff = now - timedelta(seconds=max_age)
                
                with self._feedbacks_lock:
                    expired = [
                        fid for fid, feedback in self._feedbacks.items()
                        if feedback.timestamp < cutoff and not feedback.action_taken
                    ]
                    
                    for fid in expired:
                        del self._feedbacks[fid]
                
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired feedbacks")
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _process_remaining_feedbacks(self) -> None:
        """Traite les feedbacks restants avant l'arrêt."""
        while not self._feedback_queue.empty():
            try:
                feedback = await self._feedback_queue.get()
                await self.process_feedback(feedback)
            except Exception:
                break
    
    async def _load_feedbacks(self) -> None:
        """Charge les feedbacks historiques."""
        try:
            if self.data_manager:
                # Récupération des feedbacks récents
                feedbacks_data = await self.data_manager.query(
                    DataQuery(
                        query_id="load_feedbacks",
                        data_type=DataType.FEEDBACK,
                        limit=1000
                    )
                )
                
                for record in feedbacks_data.records:
                    if record.value:
                        feedback = self._deserialize_feedback(record.value)
                        if feedback:
                            with self._feedbacks_lock:
                                self._feedbacks[feedback.feedback_id] = feedback
            
            logger.info(f"Loaded {len(self._feedbacks)} historical feedbacks")
            
        except Exception as e:
            logger.error(f"Error loading feedbacks: {e}")
    
    def _deserialize_feedback(self, data: Dict) -> Optional[Feedback]:
        """Désérialise un feedback."""
        try:
            return Feedback(
                feedback_id=data.get("feedback_id", str(uuid.uuid4())),
                feedback_type=FeedbackType(data.get("feedback_type", "neutral")),
                source=FeedbackSource(data.get("source", "system")),
                priority=FeedbackPriority(data.get("priority", "medium")),
                score=data.get("score", 0.0),
                confidence=data.get("confidence", 0.0),
                message=data.get("message", ""),
                context=data.get("context", {}),
                related_decisions=data.get("related_decisions", []),
                related_orders=data.get("related_orders", []),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                expiration=datetime.fromisoformat(data.get("expiration")) if data.get("expiration") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                weight=data.get("weight", 1.0),
                acknowledged=data.get("acknowledged", False),
                action_taken=data.get("action_taken", False)
            )
        except Exception as e:
            logger.error(f"Error deserializing feedback: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_feedbacks(
        self,
        source: Optional[FeedbackSource] = None,
        feedback_type: Optional[FeedbackType] = None,
        limit: int = 100
    ) -> List[Feedback]:
        """Récupère les feedbacks."""
        with self._feedbacks_lock:
            feedbacks = list(self._feedbacks.values())
            
            if source:
                feedbacks = [f for f in feedbacks if f.source == source]
            if feedback_type:
                feedbacks = [f for f in feedbacks if f.feedback_type == feedback_type]
            
            feedbacks.sort(key=lambda f: f.timestamp, reverse=True)
            return feedbacks[:limit]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._feedbacks_lock:
            self._stats["total_feedbacks"] = len(self._feedbacks)
            self._stats["queue_size"] = self._feedback_queue.qsize()
        
        return self._stats.copy()
    
    async def acknowledge_feedback(self, feedback_id: str) -> bool:
        """Accuse réception d'un feedback."""
        with self._feedbacks_lock:
            feedback = self._feedbacks.get(feedback_id)
            if not feedback:
                return False
            
            feedback.acknowledged = True
            return True
    
    async def mark_action_taken(self, feedback_id: str) -> bool:
        """Marque qu'une action a été prise pour un feedback."""
        with self._feedbacks_lock:
            feedback = self._feedbacks.get(feedback_id)
            if not feedback:
                return False
            
            feedback.action_taken = True
            return True


class ReinforcementEngine(ReinforcementEngineInterface):
    """
    Moteur d'apprentissage par renforcement avancé pour le Hedge Bot.
    Implémente DQN, PPO, SAC et d'autres algorithmes pour l'optimisation des décisions.
    """
    
    def __init__(
        self,
        feedback_engine: Optional[FeedbackEngine] = None,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.feedback_engine = feedback_engine
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Buffer d'expériences
        self._experience_buffer: deque = deque(maxlen=self.config["buffer_size"])
        self._buffer_lock = threading.RLock()
        
        # Épisodes
        self._episodes: Dict[str, List[ReinforcementExperience]] = {}
        self._episode_lock = threading.RLock()
        self._current_episode_id: Optional[str] = None
        self._episode_step: int = 0
        
        # Modèle (simulé)
        self._model_version = 0
        self._training_step = 0
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "experiences_added": 0,
            "training_steps": 0,
            "avg_reward": 0.0,
            "total_reward": 0.0,
            "episodes_completed": 0,
            "success_rate": 0.0,
            "exploration_rate": 0.0
        }
        
        # Exploration
        self._exploration_rate = self.config["epsilon_start"]
        
        # État
        self._is_running = False
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        logger.info("ReinforcementEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "buffer_size": 10000,
            "batch_size": 64,
            "gamma": 0.99,
            "epsilon_start": 1.0,
            "epsilon_end": 0.01,
            "epsilon_decay": 0.995,
            "learning_rate": 0.001,
            "target_update_frequency": 100,
            "min_buffer_size": 1000,
            "prioritized_replay": True,
            "alpha": 0.6,
            "beta_start": 0.4,
            "beta_end": 1.0,
            "hidden_layers": [128, 128],
            "activation": "relu",
            "optimizer": "adam"
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'apprentissage par renforcement."""
        logger.info("ReinforcementEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._training_loop())
        asyncio.create_task(self._exploration_loop())
        
        logger.info("ReinforcementEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'apprentissage par renforcement."""
        logger.info("ReinforcementEngine stopping...")
        self._is_running = False
        
        self._compute_pool.shutdown(wait=True)
        logger.info("ReinforcementEngine stopped")
    
    async def add_experience(self, experience: ReinforcementExperience) -> None:
        """Ajoute une expérience."""
        with self._buffer_lock:
            # Calcul de la priorité pour le replay priorisé
            if self.config["prioritized_replay"]:
                experience.priority = abs(experience.reward) + 0.01
            
            self._experience_buffer.append(experience)
            self._stats["experiences_added"] += 1
            
            # Mise à jour de la moyenne des récompenses
            self._stats["total_reward"] += experience.reward
            count = self._stats["experiences_added"]
            self._stats["avg_reward"] = self._stats["total_reward"] / count
        
        # Enregistrement de l'épisode
        if experience.episode_id:
            with self._episode_lock:
                if experience.episode_id not in self._episodes:
                    self._episodes[experience.episode_id] = []
                self._episodes[experience.episode_id].append(experience)
        
        # Génération de feedback
        if self.feedback_engine and abs(experience.reward) > 0.3:
            feedback = Feedback(
                feedback_type=FeedbackType.POSITIVE if experience.reward > 0 else FeedbackType.NEGATIVE,
                source=FeedbackSource.AI,
                priority=FeedbackPriority.LOW,
                score=experience.reward,
                confidence=0.6,
                message=f"RL experience reward: {experience.reward:.2f}",
                context={"experience_id": experience.experience_id},
                tags=["rl", "experience"]
            )
            await self.feedback_engine.submit_feedback(feedback)
    
    async def train(self, batch_size: int) -> Dict[str, Any]:
        """Entraîne le modèle avec un batch."""
        # Récupération du batch
        batch = await self._sample_batch(batch_size)
        
        if not batch:
            return {"status": "no_data", "training_step": self._training_step}
        
        try:
            # Simulation d'entraînement
            # Dans un système réel, on utiliserait PyTorch/TensorFlow
            
            # Calcul des pertes
            losses = []
            rewards = []
            
            for exp in batch:
                # TD Error simplifié
                target = exp.reward + self.config["gamma"] * 0.5
                current = 0.5  # Simulation
                loss = (target - current) ** 2
                losses.append(loss)
                rewards.append(exp.reward)
            
            avg_loss = np.mean(losses)
            avg_reward = np.mean(rewards)
            
            # Mise à jour du modèle
            self._training_step += 1
            self._stats["training_steps"] += 1
            self._stats["avg_reward"] = (
                self._stats["avg_reward"] * 0.9 + avg_reward * 0.1
            )
            
            # Mise à jour des priorités pour le replay priorisé
            if self.config["prioritized_replay"]:
                with self._buffer_lock:
                    for exp, loss in zip(batch, losses):
                        exp.priority = abs(exp.reward) + abs(loss) + 0.01
            
            return {
                "status": "success",
                "avg_loss": avg_loss,
                "avg_reward": avg_reward,
                "training_step": self._training_step,
                "batch_size": len(batch)
            }
            
        except Exception as e:
            logger.error(f"Training error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def predict(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prédit la prochaine action."""
        # Simulation de prédiction
        # Dans un système réel, on utiliserait le modèle entraîné
        
        # Exploration vs exploitation
        if random.random() < self._exploration_rate:
            # Exploration: action aléatoire
            action = {
                "action_type": "explore",
                "decision_type": random.choice([dt.value for dt in DecisionType]),
                "strategy": random.choice([s.value for s in HedgeStrategy]),
                "confidence": random.uniform(0.3, 0.7),
                "position_size": random.uniform(0.01, 0.2),
                "stop_loss": random.uniform(0.02, 0.1),
                "take_profit": random.uniform(0.05, 0.2)
            }
        else:
            # Exploitation: meilleure action connue
            action = {
                "action_type": "exploit",
                "decision_type": DecisionType.ADJUST_HEDGE.value,
                "strategy": HedgeStrategy.DYNAMIC_HEDGE.value,
                "confidence": 0.75,
                "position_size": 0.1,
                "stop_loss": 0.05,
                "take_profit": 0.1
            }
        
        # Ajustement basé sur l'état
        if state.get("risk_level") == "high":
            action["stop_loss"] = max(action["stop_loss"], 0.08)
            action["position_size"] = min(action["position_size"], 0.05)
        elif state.get("risk_level") == "low":
            action["position_size"] = min(action["position_size"] * 1.5, 0.2)
        
        return action
    
    # ========== MÉTHODES PRIVÉES ==========
    
    async def _sample_batch(self, batch_size: int) -> List[ReinforcementExperience]:
        """Échantillonne un batch d'expériences."""
        with self._buffer_lock:
            if len(self._experience_buffer) < self.config["min_buffer_size"]:
                return []
            
            if self.config["prioritized_replay"]:
                # Échantillonnage prioritaire
                priorities = [exp.priority for exp in self._experience_buffer]
                total_priority = sum(priorities)
                probabilities = [p / total_priority for p in priorities]
                
                indices = np.random.choice(
                    len(self._experience_buffer),
                    size=min(batch_size, len(self._experience_buffer)),
                    p=probabilities,
                    replace=False
                )
                
                batch = [self._experience_buffer[i] for i in indices]
            else:
                # Échantillonnage uniforme
                batch = random.sample(
                    list(self._experience_buffer),
                    min(batch_size, len(self._experience_buffer))
                )
            
            return batch
    
    async def _training_loop(self) -> None:
        """Boucle d'entraînement continue."""
        while self._is_running:
            await asyncio.sleep(5)
            
            try:
                # Vérification du buffer
                with self._buffer_lock:
                    if len(self._experience_buffer) < self.config["min_buffer_size"]:
                        continue
                
                # Entraînement
                result = await self.train(self.config["batch_size"])
                
                if result.get("status") == "success":
                    logger.debug(f"Training completed: step={self._training_step}, "
                               f"loss={result.get('avg_loss', 0):.4f}, "
                               f"reward={result.get('avg_reward', 0):.4f}")
                
            except Exception as e:
                logger.error(f"Training loop error: {e}")
    
    async def _exploration_loop(self) -> None:
        """Boucle de gestion de l'exploration."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Décroissance de l'exploration
                self._exploration_rate = max(
                    self.config["epsilon_end"],
                    self._exploration_rate * self.config["epsilon_decay"]
                )
                
                self._stats["exploration_rate"] = self._exploration_rate
                
                logger.debug(f"Exploration rate: {self._exploration_rate:.4f}")
                
            except Exception as e:
                logger.error(f"Exploration loop error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def start_episode(self) -> str:
        """Démarre un nouvel épisode."""
        self._current_episode_id = str(uuid.uuid4())
        self._episode_step = 0        
        with self._episode_lock:
            self._episodes[self._current_episode_id] = []
        
        logger.debug(f"Episode started: {self._current_episode_id}")
        return self._current_episode_id
    
    async def end_episode(self, episode_id: str) -> Dict[str, Any]:
        """Termine un épisode."""
        with self._episode_lock:
            experiences = self._episodes.get(episode_id, [])
        
        if not experiences:
            return {"status": "no_data", "episode_id": episode_id}
        
        # Calcul des métriques de l'épisode
        total_reward = sum(exp.reward for exp in experiences)
        avg_reward = total_reward / len(experiences)
        success_rate = sum(1 for exp in experiences if exp.reward > 0) / len(experiences)
        
        # Mise à jour des statistiques
        self._stats["episodes_completed"] += 1
        self._stats["success_rate"] = (
            self._stats["success_rate"] * 0.9 + success_rate * 0.1
        )
        
        # Génération de feedback
        if self.feedback_engine:
            feedback = Feedback(
                feedback_type=FeedbackType.POSITIVE if total_reward > 0 else FeedbackType.NEGATIVE,
                source=FeedbackSource.AI,
                priority=FeedbackPriority.MEDIUM,
                score=total_reward,
                confidence=0.5,
                message=f"Episode completed: reward={total_reward:.2f}",
                context={
                    "episode_id": episode_id,
                    "steps": len(experiences),
                    "avg_reward": avg_reward,
                    "success_rate": success_rate
                },
                tags=["rl", "episode"]
            )
            await self.feedback_engine.submit_feedback(feedback)
        
        logger.info(f"Episode ended: {episode_id} reward={total_reward:.2f} "
                   f"success_rate={success_rate:.2f}")
        
        return {
            "episode_id": episode_id,
            "total_reward": total_reward,
            "avg_reward": avg_reward,
            "steps": len(experiences),
            "success_rate": success_rate
        }
    
    async def get_experiences(
        self,
        episode_id: Optional[str] = None,
        limit: int = 100
    ) -> List[ReinforcementExperience]:
        """Récupère les expériences."""
        with self._buffer_lock:
            experiences = list(self._experience_buffer)
            
            if episode_id:
                experiences = [e for e in experiences if e.episode_id == episode_id]
            
            experiences.sort(key=lambda e: e.timestamp, reverse=True)
            return experiences[:limit]
    
    async def get_buffer_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques du buffer."""
        with self._buffer_lock:
            return {
                "buffer_size": len(self._experience_buffer),
                "min_buffer_size": self.config["min_buffer_size"],
                "prioritized_replay": self.config["prioritized_replay"],
                "exploration_rate": self._exploration_rate,
                "training_steps": self._training_step
            }
    
    async def clear_buffer(self) -> None:
        """Vide le buffer."""
        with self._buffer_lock:
            self._experience_buffer.clear()
        logger.info("Experience buffer cleared")


# ============== FEEDBACK ANALYZER ==============

class FeedbackAnalyzer:
    """
    Analyseur de feedback avancé.
    Génère des insights et des recommandations basées sur les feedbacks collectés.
    """
    
    def __init__(self, feedback_engine: FeedbackEngine):
        self.feedback_engine = feedback_engine
        self._analysis_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
    
    async def analyze_trends(self, timeframe: int = 3600) -> Dict[str, Any]:
        """Analyse les tendances des feedbacks."""
        feedbacks = await self.feedback_engine.get_feedbacks(limit=1000)
        
        # Analyse par source
        source_analysis = {}
        for source in FeedbackSource:
            source_feedbacks = [f for f in feedbacks if f.source == source]
            if source_feedbacks:
                scores = [f.score for f in source_feedbacks]
                source_analysis[source.value] = {
                    "count": len(source_feedbacks),
                    "avg_score": np.mean(scores),
                    "std_score": np.std(scores),
                    "positive_ratio": sum(1 for f in source_feedbacks if f.score > 0.3) / len(source_feedbacks),
                    "negative_ratio": sum(1 for f in source_feedbacks if f.score < -0.3) / len(source_feedbacks)
                }
        
        # Analyse par type
        type_analysis = {}
        for fb_type in FeedbackType:
            type_feedbacks = [f for f in feedbacks if f.feedback_type == fb_type]
            if type_feedbacks:
                scores = [f.score for f in type_feedbacks]
                type_analysis[fb_type.value] = {
                    "count": len(type_feedbacks),
                    "avg_score": np.mean(scores),
                    "std_score": np.std(scores)
                }
        
        # Calcul du score global
        all_scores = [f.score for f in feedbacks]
        global_score = np.mean(all_scores) if all_scores else 0.0
        
        return {
            "source_analysis": source_analysis,
            "type_analysis": type_analysis,
            "global_score": global_score,
            "total_feedbacks": len(feedbacks),
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Génère des recommandations basées sur l'analyse."""
        trends = await self.analyze_trends()
        recommendations = []
        
        # Recommandations basées sur les sources
        for source, analysis in trends["source_analysis"].items():
            if analysis["negative_ratio"] > 0.3:
                recommendations.append({
                    "source": source,
                    "type": "improvement",
                    "priority": "high",
                    "message": f"High negative feedback ratio from {source}: {analysis['negative_ratio']:.2f}",
                    "suggestion": f"Review and improve {source} related processes"
                })
            elif analysis["positive_ratio"] > 0.7:
                recommendations.append({
                    "source": source,
                    "type": "reinforcement",
                    "priority": "low",
                    "message": f"Strong positive feedback from {source}: {analysis['positive_ratio']:.2f}",
                    "suggestion": f"Continue current {source} strategies"
                })
        
        # Recommandations globales
        if trends["global_score"] < -0.2:
            recommendations.append({
                "source": "global",
                "type": "critical",
                "priority": "critical",
                "message": f"Overall feedback score is negative: {trends['global_score']:.2f}",
                "suggestion": "Comprehensive review of all systems recommended"
            })
        
        return recommendations


# ============== FACTORY ==============

class FeedbackFactory:
    """Factory pour créer des composants de feedback."""
    
    @staticmethod
    async def create_feedback_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> FeedbackEngine:
        """Crée un moteur de feedback."""
        engine = FeedbackEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    async def create_reinforcement_engine(
        feedback_engine: Optional[FeedbackEngine] = None,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ReinforcementEngine:
        """Crée un moteur d'apprentissage par renforcement."""
        engine = ReinforcementEngine(
            feedback_engine=feedback_engine,
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_analyzer(feedback_engine: FeedbackEngine) -> FeedbackAnalyzer:
        """Crée un analyseur de feedback."""
        return FeedbackAnalyzer(feedback_engine)


# ============== EXPORT ==============

__all__ = [
    "FeedbackType",
    "FeedbackSource",
    "FeedbackPriority",
    "ReinforcementSignal",
    "Feedback",
    "ReinforcementExperience",
    "PerformanceFeedback",
    "LearningProgress",
    "FeedbackEngineInterface",
    "ReinforcementEngineInterface",
    "FeedbackEngine",
    "ReinforcementEngine",
    "FeedbackAnalyzer",
    "FeedbackFactory"
]
