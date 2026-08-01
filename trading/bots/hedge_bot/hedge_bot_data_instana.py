# trading/bots/hedge_bot/hedge_bot_data_instana.py
# Advanced Instana Integration & Observability Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Instana Integration Module - Module d'intégration avancé avec Instana pour le Hedge Bot.
Assure l'observabilité complète, le tracing distribué, la surveillance des performances,
l'analyse des métriques et le monitoring des transactions pour l'ensemble du système de hedging.
"""

import asyncio
import json
import time
import hashlib
import uuid as uuid_lib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import aiohttp
import aiohttp.client_exceptions
from collections import defaultdict, deque
import threading
import concurrent.futures

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_instana")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult
)


# ============== ENUMS & TYPES ==============

class InstanaSpanType(Enum):
    """Types de spans Instana."""
    ENTRY = "entry"
    EXIT = "exit"
    LOCAL = "local"
    INTERMEDIATE = "intermediate"
    ASYNC = "async"


class InstanaServiceType(Enum):
    """Types de services Instana."""
    HEDGE_BOT = "hedge_bot"
    TRADING_ENGINE = "trading_engine"
    RISK_ENGINE = "risk_engine"
    DECISION_ENGINE = "decision_engine"
    EXECUTION_ENGINE = "execution_engine"
    DATA_LAYER = "data_layer"
    API_GATEWAY = "api_gateway"
    STREAMING = "streaming"


class InstanaEventLevel(Enum):
    """Niveaux d'événements Instana."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    DEBUG = "debug"


# ============== DATA MODELS ==============

@dataclass
class InstanaSpan:
    """Span Instana pour le tracing distribué."""
    span_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    parent_id: Optional[str] = None
    name: str = ""
    service: str = ""
    span_type: InstanaSpanType = InstanaSpanType.LOCAL
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)
    baggage: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    error: bool = False
    error_details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "service": self.service,
            "span_type": self.span_type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "baggage": self.baggage,
            "logs": self.logs,
            "error": self.error,
            "error_details": self.error_details,
            "metadata": self.metadata,
            "children": self.children
        }


@dataclass
class InstanaMetric:
    """Métrique Instana."""
    metric_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    name: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    aggregation: str = "gauge"  # gauge, counter, histogram, sum, avg
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstanaTrace:
    """Trace Instana."""
    trace_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    spans: List[InstanaSpan] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    service: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstanaEvent:
    """Événement Instana."""
    event_id: str = field(default_factory=lambda: str(uuid_lib.uuid4()))
    level: InstanaEventLevel = InstanaEventLevel.INFO
    message: str = ""
    service: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class InstanaIntegrationInterface(ABC):
    """Interface abstraite pour l'intégration Instana."""
    
    @abstractmethod
    async def start_span(self, span: InstanaSpan) -> str:
        """Démarre une span."""
        pass
    
    @abstractmethod
    async def finish_span(self, span_id: str) -> bool:
        """Termine une span."""
        pass
    
    @abstractmethod
    async def send_metric(self, metric: InstanaMetric) -> bool:
        """Envoie une métrique."""
        pass
    
    @abstractmethod
    async def send_event(self, event: InstanaEvent) -> bool:
        """Envoie un événement."""
        pass


# ============== IMPLÉMENTATION ==============

class InstanaIntegration(InstanaIntegrationInterface):
    """
    Intégration avancée avec Instana pour le Hedge Bot.
    Gère le tracing distribué, les métriques, les événements et l'observabilité.
    """
    
    def __init__(
        self,
        api_token: str,
        agent_host: str = "localhost",
        agent_port: int = 42699,
        service_name: str = "hedge_bot",
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.api_token = api_token
        self.agent_host = agent_host
        self.agent_port = agent_port
        self.service_name = service_name
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Base URL pour l'agent Instana
        self.agent_url = f"http://{agent_host}:{agent_port}/com.instana.plugin.generic.trace"
        self.metric_url = f"http://{agent_host}:{agent_port}/com.instana.plugin.generic.metric"
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Gestion des spans
        self._active_spans: Dict[str, InstanaSpan] = {}
        self._spans_lock = threading.RLock()
        
        # Gestion des traces
        self._traces: Dict[str, InstanaTrace] = {}
        self._traces_lock = threading.RLock()
        
        # Queue des spans
        self._span_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "spans_started": 0,
            "spans_finished": 0,
            "metrics_sent": 0,
            "events_sent": 0,
            "errors": 0,
            "active_spans": 0,
            "avg_span_duration": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("InstanaIntegration initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "batch_size": 100,
            "flush_interval": 5,
            "max_spans_per_trace": 1000,
            "enable_tracing": True,
            "enable_metrics": True,
            "enable_events": True,
            "sampling_rate": 1.0,
            "error_sampling_rate": 1.0,
            "cache_size": 1000,
            "timeout": 30,
            "retry_count": 3,
            "retry_delay": 1.0,
            "max_span_duration_ms": 60000
        }
    
    async def start(self) -> None:
        """Démarre l'intégration Instana."""
        logger.info("InstanaIntegration starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"apiToken {self.api_token}",
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=self.config["timeout"])
        )
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._span_processor())
        asyncio.create_task(self._trace_cleaner())
        
        logger.info("InstanaIntegration started")
    
    async def stop(self) -> None:
        """Arrête l'intégration Instana."""
        logger.info("InstanaIntegration stopping...")
        self._is_running = False
        
        # Vidage de la queue
        await self._flush_spans()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("InstanaIntegration stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def start_span(self, span: InstanaSpan) -> str:
        """Démarre une span."""
        if not self.config["enable_tracing"]:
            return span.span_id
        
        # Échantillonnage
        if not self._should_sample():
            return span.span_id
        
        with self._spans_lock:
            self._active_spans[span.span_id] = span
            self._stats["spans_started"] += 1
            self._stats["active_spans"] = len(self._active_spans)
        
        # Stockage du span
        await self._span_queue.put(span)
        
        logger.debug(f"Span started: {span.name} (id={span.span_id})")
        return span.span_id
    
    async def finish_span(self, span_id: str) -> bool:
        """Termine une span."""
        if not self.config["enable_tracing"]:
            return True
        
        with self._spans_lock:
            span = self._active_spans.get(span_id)
            if not span:
                return False
            
            span.end_time = datetime.now(timezone.utc)
            span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
            self._stats["spans_finished"] += 1
            self._stats["active_spans"] = len(self._active_spans) - 1
            
            # Mise à jour de la durée moyenne
            self._stats["avg_span_duration"] = (
                self._stats["avg_span_duration"] * 0.9 + span.duration_ms * 0.1
            )
            
            # Suppression de la span active
            del self._active_spans[span_id]
        
        # Mise en queue pour envoi
        await self._span_queue.put(span)
        
        logger.debug(f"Span finished: {span.name} duration={span.duration_ms:.2f}ms")
        return True
    
    async def send_metric(self, metric: InstanaMetric) -> bool:
        """Envoie une métrique."""
        if not self.config["enable_metrics"]:
            return True
        
        try:
            # Construction du payload
            payload = {
                "service": self.service_name,
                "metrics": [
                    {
                        "name": metric.name,
                        "value": metric.value,
                        "timestamp": int(metric.timestamp.timestamp() * 1000),
                        "dimensions": metric.dimensions,
                        "unit": metric.unit,
                        "aggregation": metric.aggregation
                    }
                ]
            }
            
            # Envoi à Instana
            async with self._session.post(
                self.metric_url,
                json=payload
            ) as response:
                if response.status in [200, 202]:
                    self._stats["metrics_sent"] += 1
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Metric send error: {response.status} - {error_text}")
                    self._stats["errors"] += 1
                    return False
                    
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Metric send error: {e}")
            return False
    
    async def send_event(self, event: InstanaEvent) -> bool:
        """Envoie un événement."""
        if not self.config["enable_events"]:
            return True
        
        try:
            # Construction du payload
            payload = {
                "service": self.service_name,
                "level": event.level.value,
                "message": event.message,
                "timestamp": int(event.timestamp.timestamp() * 1000),
                "tags": event.tags,
                "metadata": event.metadata
            }
            
            # Envoi à Instana (via les spans)
            # Dans un système réel, on utiliserait l'API événements Instana
            self._stats["events_sent"] += 1
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Event send error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - TRAITEMENT ==========
    
    async def _span_processor(self) -> None:
        """Traite les spans en batch."""
        while self._is_running:
            try:
                spans = []
                start_time = time.time()
                
                # Collecte des spans
                while len(spans) < self.config["batch_size"]:
                    try:
                        span = await asyncio.wait_for(
                            self._span_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        spans.append(span)
                    except asyncio.TimeoutError:
                        break
                
                if spans:
                    # Envoi des spans
                    await self._send_spans_batch(spans)
                
                # Gestion du temps restant
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Span processor error: {e}")
                await asyncio.sleep(1)
    
    async def _send_spans_batch(self, spans: List[InstanaSpan]) -> bool:
        """Envoie un batch de spans."""
        try:
            # Construction du payload
            spans_data = []
            for span in spans:
                span_data = {
                    "id": span.span_id,
                    "traceId": span.trace_id,
                    "parentId": span.parent_id,
                    "name": span.name,
                    "service": span.service or self.service_name,
                    "type": span.span_type.value,
                    "timestamp": int(span.start_time.timestamp() * 1000),
                    "duration": int(span.duration_ms * 1000),  # microsecondes
                    "error": span.error,
                    "tags": span.tags,
                    "baggage": span.baggage,
                    "logs": span.logs
                }
                
                # Ajout des erreurs
                if span.error and span.error_details:
                    span_data["errorDetails"] = span.error_details
                
                spans_data.append(span_data)
            
            # Envoi à Instana
            payload = {
                "spans": spans_data,
                "service": self.service_name
            }
            
            async with self._session.post(
                self.agent_url,
                json=payload
            ) as response:
                if response.status in [200, 202]:
                    logger.debug(f"Sent {len(spans)} spans to Instana")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Span send error: {response.status} - {error_text}")
                    self._stats["errors"] += 1
                    return False
                    
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Span batch send error: {e}")
            return False
    
    async def _flush_spans(self) -> None:
        """Vide la queue des spans."""
        spans = []
        while not self._span_queue.empty():
            try:
                span = self._span_queue.get_nowait()
                spans.append(span)
            except asyncio.QueueEmpty:
                break
        
        if spans:
            await self._send_spans_batch(spans)
    
    async def _trace_cleaner(self) -> None:
        """Nettoie les traces inactives."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._traces_lock:
                    now = datetime.now(timezone.utc)
                    for trace_id in list(self._traces.keys()):
                        trace = self._traces[trace_id]
                        age = (now - trace.start_time).total_seconds()
                        if age > 3600:  # 1 heure
                            del self._traces[trace_id]
                
            except Exception as e:
                logger.error(f"Trace cleaner error: {e}")
    
    def _should_sample(self) -> bool:
        """Vérifie si la span doit être échantillonnée."""
        import random
        return random.random() < self.config["sampling_rate"]
    
    # ========== MÉTHODES SPÉCIFIQUES HEDGE BOT ==========
    
    async def trace_decision(
        self,
        decision: Decision,
        context: Dict[str, Any]
    ) -> InstanaSpan:
        """Trace une décision de hedging."""
        span = InstanaSpan(
            name=f"decision.{decision.decision_type.value}",
            service=self.service_name,
            span_type=InstanaSpanType.LOCAL,
            tags={
                "decision_id": decision.decision_id,
                "decision_type": decision.decision_type.value,
                "confidence": decision.confidence,
                "strategy": decision.strategy.value,
                "target_asset": decision.target_asset,
                "target_amount": decision.target_amount,
                "target_price": decision.target_price
            },
            baggage={
                "hedge_type": decision.decision_type.value,
                "correlation_id": context.get("correlation_id", "")
            },
            metadata=context
        )
        
        await self.start_span(span)
        return span
    
    async def trace_execution(
        self,
        order_id: str,
        execution_data: Dict[str, Any]
    ) -> InstanaSpan:
        """Trace une exécution de trade."""
        span = InstanaSpan(
            name="execution.trade",
            service=self.service_name,
            span_type=InstanaSpanType.EXIT,
            tags={
                "order_id": order_id,
                "symbol": execution_data.get("symbol", ""),
                "side": execution_data.get("side", ""),
                "quantity": execution_data.get("quantity", 0),
                "price": execution_data.get("price", 0),
                "status": execution_data.get("status", ""),
                "filled_quantity": execution_data.get("filled_quantity", 0)
            },
            baggage={
                "correlation_id": execution_data.get("correlation_id", "")
            }
        )
        
        await self.start_span(span)
        return span
    
    async def trace_risk_calculation(
        self,
        symbol: str,
        risk_metrics: Dict[str, Any]
    ) -> InstanaSpan:
        """Trace un calcul de risque."""
        span = InstanaSpan(
            name="risk.calculation",
            service=self.service_name,
            span_type=InstanaSpanType.LOCAL,
            tags={
                "symbol": symbol,
                "var": risk_metrics.get("var", 0),
                "drawdown": risk_metrics.get("drawdown", 0),
                "sharpe": risk_metrics.get("sharpe", 0),
                "volatility": risk_metrics.get("volatility", 0)
            }
        )
        
        await self.start_span(span)
        return span
    
    async def trace_market_data(
        self,
        symbol: str,
        market_data: Dict[str, Any]
    ) -> InstanaSpan:
        """Trace une requête de données de marché."""
        span = InstanaSpan(
            name="market_data.query",
            service=self.service_name,
            span_type=InstanaSpanType.ENTRY,
            tags={
                "symbol": symbol,
                "price": market_data.get("price", 0),
                "volume": market_data.get("volume", 0),
                "timestamp": market_data.get("timestamp", "")
            }
        )
        
        await self.start_span(span)
        return span
    
    async def create_trace_context(self) -> InstanaTrace:
        """Crée un contexte de trace."""
        trace = InstanaTrace(
            service=self.service_name,
            tags={
                "environment": self.config.get("environment", "production"),
                "version": self.config.get("version", "1.0.0")
            }
        )
        
        with self._traces_lock:
            self._traces[trace.trace_id] = trace
        
        return trace
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_trace(self, trace_id: str) -> Optional[InstanaTrace]:
        """Récupère une trace."""
        with self._traces_lock:
            return self._traces.get(trace_id)
    
    async def get_traces(self, limit: int = 100) -> List[InstanaTrace]:
        """Récupère les traces récentes."""
        with self._traces_lock:
            traces = list(self._traces.values())
            traces.sort(key=lambda t: t.start_time, reverse=True)
            return traces[:limit]
    
    async def get_active_spans(self) -> List[InstanaSpan]:
        """Récupère les spans actives."""
        with self._spans_lock:
            return list(self._active_spans.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._spans_lock:
            self._stats["active_spans"] = len(self._active_spans)
        
        return self._stats.copy()


# ============== TRACE CONTEXT MANAGER ==============

class TraceContext:
    """
    Context manager pour le tracing distribué.
    Gère les traces et les spans automatiquement.
    """
    
    def __init__(
        self,
        integration: InstanaIntegration,
        name: str,
        span_type: InstanaSpanType = InstanaSpanType.LOCAL,
        tags: Optional[Dict[str, Any]] = None
    ):
        self.integration = integration
        self.name = name
        self.span_type = span_type
        self.tags = tags or {}
        self.span: Optional[InstanaSpan] = None
    
    async def __aenter__(self):
        # Création de la span
        self.span = InstanaSpan(
            name=self.name,
            service=self.integration.service_name,
            span_type=self.span_type,
            tags=self.tags
        )
        
        # Démarrage de la span
        await self.integration.start_span(self.span)
        return self.span
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.error = True
                self.span.error_details = str(exc_val) if exc_val else "Unknown error"
                self.span.tags["error_type"] = exc_type.__name__
            
            await self.integration.finish_span(self.span.span_id)
            return exc_type is None


# ============== FACTORY ==============

class InstanaFactory:
    """Factory pour créer des composants Instana."""
    
    @staticmethod
    async def create_integration(
        api_token: str,
        agent_host: str = "localhost",
        agent_port: int = 42699,
        service_name: str = "hedge_bot",
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> InstanaIntegration:
        """Crée une intégration Instana."""
        integration = InstanaIntegration(
            api_token=api_token,
            agent_host=agent_host,
            agent_port=agent_port,
            service_name=service_name,
            data_manager=data_manager,
            config=config
        )
        await integration.start()
        return integration
    
    @staticmethod
    def create_trace_context(
        integration: InstanaIntegration,
        name: str,
        span_type: InstanaSpanType = InstanaSpanType.LOCAL,
        tags: Optional[Dict[str, Any]] = None
    ) -> TraceContext:
        """Crée un contexte de trace."""
        return TraceContext(integration, name, span_type, tags)


# ============== EXPORT ==============

__all__ = [
    "InstanaSpanType",
    "InstanaServiceType",
    "InstanaEventLevel",
    "InstanaSpan",
    "InstanaMetric",
    "InstanaTrace",
    "InstanaEvent",
    "InstanaIntegrationInterface",
    "InstanaIntegration",
    "TraceContext",
    "InstanaFactory"
]
