# trading/bots/hedge_bot/hedge_bot_data_dynatrace.py
# Advanced Dynatrace Integration for Hedge Bot Monitoring & Observability
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Dynatrace Integration - Module d'intégration avancé avec Dynatrace pour le Hedge Bot.
Assure une observabilité complète, du monitoring en temps réel, des alertes intelligentes
et des analyses de performance pour l'ensemble du système de hedging.
"""

import asyncio
import json
import time
import hashlib
import socket
import os
import platform
import psutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import aiohttp
import aiohttp.client_exceptions
from collections import defaultdict, deque
import statistics
import threading
import queue

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_dynatrace")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class DynatraceEventType(Enum):
    """Types d'événements Dynatrace."""
    CUSTOM = "CUSTOM"
    APPLICATION = "APPLICATION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    DEPLOYMENT = "DEPLOYMENT"
    AVAILABILITY = "AVAILABILITY"
    ERROR = "ERROR"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    TRADING = "TRADING"
    HEDGE = "HEDGE"
    RISK = "RISK"
    DECISION = "DECISION"


class DynatraceSeverity(Enum):
    """Niveaux de sévérité Dynatrace."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class DynatraceMetricType(Enum):
    """Types de métriques Dynatrace."""
    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"
    SUMMARY = "SUMMARY"


class DynatraceEntityType(Enum):
    """Types d'entités Dynatrace."""
    SERVICE = "SERVICE"
    PROCESS = "PROCESS"
    HOST = "HOST"
    APPLICATION = "APPLICATION"
    CUSTOM = "CUSTOM"
    TRADING_SYSTEM = "TRADING_SYSTEM"
    HEDGE_BOT = "HEDGE_BOT"
    RISK_ENGINE = "RISK_ENGINE"
    DECISION_ENGINE = "DECISION_ENGINE"


# ============== DATA MODELS ==============

@dataclass
class DynatraceEvent:
    """Modèle d'événement Dynatrace."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: DynatraceEventType = DynatraceEventType.CUSTOM
    severity: DynatraceSeverity = DynatraceSeverity.INFO
    title: str = ""
    message: str = ""
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    entity_id: Optional[str] = None
    correlation_id: Optional[str] = None
    dimensions: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "properties": self.properties,
            "entityId": self.entity_id,
            "correlationId": self.correlation_id,
            "dimensions": self.dimensions
        }


@dataclass
class DynatraceMetric:
    """Modèle de métrique Dynatrace."""
    metric_id: str
    name: str
    value: float
    metric_type: DynatraceMetricType = DynatraceMetricType.GAUGE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "metricId": self.metric_id,
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "dimensions": self.dimensions,
            "unit": self.unit,
            "tags": self.tags
        }


@dataclass
class DynatraceEntity:
    """Modèle d'entité Dynatrace."""
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: DynatraceEntityType = DynatraceEntityType.CUSTOM
    display_name: str = ""
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    health_status: str = "OK"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        return {
            "entityId": self.entity_id,
            "entityType": self.entity_type.value,
            "displayName": self.display_name,
            "tags": self.tags,
            "properties": self.properties,
            "healthStatus": self.health_status,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat()
        }


@dataclass
class DynatraceTransaction:
    """Modèle de transaction Dynatrace."""
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    duration: float = 0.0
    success: bool = True
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    service: str = ""
    method: str = ""
    url: str = ""
    status_code: int = 200
    tags: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    parent_transaction_id: Optional[str] = None
    spans: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "transactionId": self.transaction_id,
            "name": self.name,
            "duration": self.duration,
            "success": self.success,
            "startTime": self.start_time.isoformat(),
            "endTime": self.end_time.isoformat() if self.end_time else None,
            "service": self.service,
            "method": self.method,
            "url": self.url,
            "statusCode": self.status_code,
            "tags": self.tags,
            "properties": self.properties,
            "parentTransactionId": self.parent_transaction_id,
            "spans": self.spans
        }


# ============== INTERFACES ==============

class DynatraceIntegrationInterface:
    """Interface abstraite pour l'intégration Dynatrace."""
    
    @abstractmethod
    async def send_event(self, event: DynatraceEvent) -> bool:
        """Envoie un événement à Dynatrace."""
        pass
    
    @abstractmethod
    async def send_metric(self, metric: DynatraceMetric) -> bool:
        """Envoie une métrique à Dynatrace."""
        pass
    
    @abstractmethod
    async def send_transaction(self, transaction: DynatraceTransaction) -> bool:
        """Envoie une transaction à Dynatrace."""
        pass
    
    @abstractmethod
    async def get_metrics(self, metric_selector: str) -> List[DynatraceMetric]:
        """Récupère des métriques depuis Dynatrace."""
        pass
    
    @abstractmethod
    async def get_entities(self, entity_selector: str) -> List[DynatraceEntity]:
        """Récupère des entités depuis Dynatrace."""
        pass


# ============== IMPLÉMENTATION ==============

class DynatraceIntegration(DynatraceIntegrationInterface):
    """
    Intégration avancée avec Dynatrace pour le Hedge Bot.
    Gère l'observabilité, le monitoring, les alertes et les analyses de performance.
    """
    
    def __init__(
        self,
        api_token: str,
        environment_url: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.api_token = api_token
        self.environment_url = environment_url.rstrip('/')
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Queue d'événements
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._metric_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._transaction_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Cache
        self._entity_cache: Dict[str, DynatraceEntity] = {}
        self._metric_cache: Dict[str, List[DynatraceMetric]] = {}
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "events_sent": 0,
            "metrics_sent": 0,
            "transactions_sent": 0,
            "events_failed": 0,
            "metrics_failed": 0,
            "transactions_failed": 0,
            "last_event_time": None,
            "last_metric_time": None,
            "last_transaction_time": None,
            "queue_sizes": {
                "events": 0,
                "metrics": 0,
                "transactions": 0
            }
        }
        
        # Thread pools
        self._io_executor = ThreadPoolExecutor(max_workers=10)
        
        # État de la connexion
        self._is_running = False
        self._health_status = "UNKNOWN"
        
        # Métriques système
        self._system_metrics = {}
        
        logger.info("DynatraceIntegration initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "batch_size": 100,
            "flush_interval": 10,  # secondes
            "retry_count": 3,
            "retry_delay": 1.0,
            "timeout": 30.0,
            "max_queue_size": 10000,
            "enable_compression": True,
            "enable_batching": True,
            "auto_discovery": True,
            "system_metrics_interval": 60,  # secondes
            "health_check_interval": 30,
            "entities": {
                "auto_create": True,
                "update_interval": 300
            },
            "transactions": {
                "enable_tracing": True,
                "sample_rate": 1.0,
                "error_sampling_rate": 1.0
            },
            "metrics": {
                "prefix": "nexus.hedge_bot",
                "include_system_metrics": True,
                "include_trading_metrics": True,
                "include_risk_metrics": True
            }
        }
    
    async def start(self) -> None:
        """Démarre l'intégration Dynatrace."""
        logger.info("DynatraceIntegration starting...")
        
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Api-Token {self.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=self.config["timeout"])
        )
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._event_processor())
        asyncio.create_task(self._metric_processor())
        asyncio.create_task(self._transaction_processor())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._system_metrics_loop())
        asyncio.create_task(self._entity_management_loop())
        
        # Auto-découverte
        if self.config["auto_discovery"]:
            await self._auto_discover_entities()
        
        # Vérification de la connexion
        if await self._test_connection():
            self._health_status = "HEALTHY"
            logger.info("DynatraceIntegration started successfully")
        else:
            self._health_status = "UNHEALTHY"
            logger.warning("DynatraceIntegration started but connection test failed")
    
    async def stop(self) -> None:
        """Arrête l'intégration Dynatrace."""
        logger.info("DynatraceIntegration stopping...")
        
        self._is_running = False
        
        # Vidage des queues
        await self._flush_all_queues()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._io_executor.shutdown(wait=True)
        logger.info("DynatraceIntegration stopped")
    
    async def send_event(self, event: DynatraceEvent) -> bool:
        """Envoie un événement à Dynatrace."""
        if not self._is_running:
            logger.warning("DynatraceIntegration not running, event queued")
            return await self._queue_event(event)
        
        try:
            # Enrichissement de l'événement
            await self._enrich_event(event)
            
            # Mise en queue
            if self.config["enable_batching"]:
                return await self._queue_event(event)
            else:
                return await self._send_event_immediate(event)
            
        except Exception as e:
            self._stats["events_failed"] += 1
            logger.error(f"Error sending event: {e}")
            return False
    
    async def send_metric(self, metric: DynatraceMetric) -> bool:
        """Envoie une métrique à Dynatrace."""
        if not self._is_running:
            logger.warning("DynatraceIntegration not running, metric queued")
            return await self._queue_metric(metric)
        
        try:
            # Enrichissement de la métrique
            await self._enrich_metric(metric)
            
            # Mise en queue
            if self.config["enable_batching"]:
                return await self._queue_metric(metric)
            else:
                return await self._send_metric_immediate(metric)
            
        except Exception as e:
            self._stats["metrics_failed"] += 1
            logger.error(f"Error sending metric: {e}")
            return False
    
    async def send_transaction(self, transaction: DynatraceTransaction) -> bool:
        """Envoie une transaction à Dynatrace."""
        if not self._is_running:
            logger.warning("DynatraceIntegration not running, transaction queued")
            return await self._queue_transaction(transaction)
        
        try:
            # Enrichissement de la transaction
            await self._enrich_transaction(transaction)
            
            # Mise en queue
            if self.config["enable_batching"]:
                return await self._queue_transaction(transaction)
            else:
                return await self._send_transaction_immediate(transaction)
            
        except Exception as e:
            self._stats["transactions_failed"] += 1
            logger.error(f"Error sending transaction: {e}")
            return False
    
    async def get_metrics(self, metric_selector: str) -> List[DynatraceMetric]:
        """Récupère des métriques depuis Dynatrace."""
        try:
            url = f"{self.environment_url}/api/v2/metrics/query"
            params = {
                "metricSelector": metric_selector,
                "resolution": "1m",
                "from": "now-1h",
                "to": "now"
            }
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    metrics = self._parse_metrics_response(data)
                    return metrics
                else:
                    logger.error(f"Error getting metrics: {response.status} - {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return []
    
    async def get_entities(self, entity_selector: str) -> List[DynatraceEntity]:
        """Récupère des entités depuis Dynatrace."""
        try:
            url = f"{self.environment_url}/api/v2/entities"
            params = {
                "entitySelector": entity_selector,
                "from": "now-1h"
            }
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    entities = self._parse_entities_response(data)
                    return entities
                else:
                    logger.error(f"Error getting entities: {response.status} - {await response.text()}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting entities: {e}")
            return []
    
    # ========== MÉTHODES DE MONITORING SPÉCIFIQUES ==========
    
    async def report_decision(self, decision: Decision) -> None:
        """Rapporte une décision de hedging à Dynatrace."""
        event = DynatraceEvent(
            event_type=DynatraceEventType.DECISION,
            severity=DynatraceSeverity.INFO,
            title=f"Hedge Decision: {decision.decision_type.value}",
            message=f"Decision made with confidence {decision.confidence:.2f}",
            source="HedgeDecisionEngine",
            tags=["hedge", "decision", decision.decision_type.value],
            properties={
                "decision_id": decision.decision_id,
                "decision_type": decision.decision_type.value,
                "confidence": decision.confidence,
                "strategy": decision.strategy.value,
                "target_asset": decision.target_asset,
                "target_amount": decision.target_amount,
                "target_price": decision.target_price,
                "reason": decision.reason
            }
        )
        await self.send_event(event)
        
        # Métrique de décision
        metric = DynatraceMetric(
            metric_id="hedge.decisions.total",
            name="Hedge Decisions Total",
            value=1.0,
            metric_type=DynatraceMetricType.COUNTER,
            dimensions={
                "decision_type": decision.decision_type.value,
                "strategy": decision.strategy.value
            },
            unit="count"
        )
        await self.send_metric(metric)
    
    async def report_decision_result(self, result: DecisionResult) -> None:
        """Rapporte le résultat d'une décision de hedging à Dynatrace."""
        severity = DynatraceSeverity.INFO if result.executed else DynatraceSeverity.ERROR
        
        event = DynatraceEvent(
            event_type=DynatraceEventType.DECISION,
            severity=severity,
            title=f"Hedge Decision Result: {result.decision.decision_type.value}",
            message=f"Decision {'executed' if result.executed else 'failed'} in {result.execution_time:.3f}s",
            source="HedgeDecisionEngine",
            tags=["hedge", "decision", "result"],
            properties={
                "decision_id": result.decision.decision_id,
                "executed": result.executed,
                "execution_time": result.execution_time,
                "error": result.error,
                "result_data": result.result_data
            }
        )
        await self.send_event(event)
        
        # Métriques de performance
        if result.executed:
            metric = DynatraceMetric(
                metric_id="hedge.decisions.executed",
                name="Hedge Decisions Executed",
                value=1.0,
                metric_type=DynatraceMetricType.COUNTER,
                dimensions={
                    "decision_type": result.decision.decision_type.value
                },
                unit="count"
            )
            await self.send_metric(metric)
        
        # Temps d'exécution
        metric = DynatraceMetric(
            metric_id="hedge.decisions.execution_time",
            name="Hedge Decision Execution Time",
            value=result.execution_time,
            metric_type=DynatraceMetricType.HISTOGRAM,
            dimensions={
                "decision_type": result.decision.decision_type.value
            },
            unit="s"
        )
        await self.send_metric(metric)
    
    async def report_risk_metrics(self, risk_metrics: Dict[str, Any]) -> None:
        """Rapporte les métriques de risque à Dynatrace."""
        # Événement de risque
        severity = DynatraceSeverity.INFO
        if risk_metrics.get("risk_level") == "high":
            severity = DynatraceSeverity.WARNING
        elif risk_metrics.get("risk_level") == "critical":
            severity = DynatraceSeverity.CRITICAL
        
        event = DynatraceEvent(
            event_type=DynatraceEventType.RISK,
            severity=severity,
            title=f"Risk Metrics Update",
            message=f"Risk score: {risk_metrics.get('risk_score', 0.0):.2f}",
            source="RiskEngine",
            tags=["hedge", "risk"],
            properties=risk_metrics
        )
        await self.send_event(event)
        
        # Métriques de risque
        for key, value in risk_metrics.items():
            if isinstance(value, (int, float)):
                metric = DynatraceMetric(
                    metric_id=f"hedge.risk.{key}",
                    name=f"Hedge Risk {key}",
                    value=float(value),
                    metric_type=DynatraceMetricType.GAUGE,
                    unit=""
                )
                await self.send_metric(metric)
    
    async def report_trade(self, trade: Dict[str, Any]) -> None:
        """Rapporte une transaction de trading à Dynatrace."""
        event = DynatraceEvent(
            event_type=DynatraceEventType.TRADING,
            severity=DynatraceSeverity.INFO,
            title=f"Trade Executed: {trade.get('symbol', 'unknown')}",
            message=f"Trade {trade.get('side', '')} {trade.get('amount', 0)} at {trade.get('price', 0)}",
            source="ExecutionEngine",
            tags=["hedge", "trade", trade.get('side', '')],
            properties=trade
        )
        await self.send_event(event)
        
        # Métriques de trading
        metric = DynatraceMetric(
            metric_id="hedge.trades.volume",
            name="Hedge Trade Volume",
            value=float(trade.get("amount", 0)),
            metric_type=DynatraceMetricType.COUNTER,
            dimensions={
                "symbol": trade.get("symbol", "unknown"),
                "side": trade.get("side", "unknown")
            },
            unit="units"
        )
        await self.send_metric(metric)
    
    async def report_performance(self, performance: Dict[str, Any]) -> None:
        """Rapporte les métriques de performance à Dynatrace."""
        event = DynatraceEvent(
            event_type=DynatraceEventType.PERFORMANCE,
            severity=DynatraceSeverity.INFO,
            title="Performance Update",
            message=f"PnL: {performance.get('pnl', 0.0):.2f}",
            source="PerformanceMonitor",
            tags=["hedge", "performance"],
            properties=performance
        )
        await self.send_event(event)
        
        # Métriques de performance
        metrics = {
            "hedge.pnl": performance.get("pnl", 0.0),
            "hedge.sharpe": performance.get("sharpe", 0.0),
            "hedge.drawdown": performance.get("drawdown", 0.0),
            "hedge.win_rate": performance.get("win_rate", 0.0),
            "hedge.profit_factor": performance.get("profit_factor", 0.0)
        }
        
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                metric = DynatraceMetric(
                    metric_id=key,
                    name=f"Hedge {key.split('.')[1].capitalize()}",
                    value=float(value),
                    metric_type=DynatraceMetricType.GAUGE,
                    unit=""
                )
                await self.send_metric(metric)
    
    # ========== MÉTHODES PRIVÉES - PROCESSING ==========
    
    async def _event_processor(self) -> None:
        """Traite les événements en batch."""
        while self._is_running:
            try:
                events = []
                start_time = time.time()
                
                # Collecte des événements
                while len(events) < self.config["batch_size"]:
                    try:
                        event = await asyncio.wait_for(
                            self._event_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        events.append(event)
                    except asyncio.TimeoutError:
                        break
                
                # Envoi des événements
                if events:
                    await self._send_events_batch(events)
                
                # Mise à jour des stats
                self._stats["queue_sizes"]["events"] = self._event_queue.qsize()
                
                # Gestion du temps restant
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
                await asyncio.sleep(1)
    
    async def _metric_processor(self) -> None:
        """Traite les métriques en batch."""
        while self._is_running:
            try:
                metrics = []
                start_time = time.time()
                
                # Collecte des métriques
                while len(metrics) < self.config["batch_size"]:
                    try:
                        metric = await asyncio.wait_for(
                            self._metric_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        metrics.append(metric)
                    except asyncio.TimeoutError:
                        break
                
                # Envoi des métriques
                if metrics:
                    await self._send_metrics_batch(metrics)
                
                # Mise à jour des stats
                self._stats["queue_sizes"]["metrics"] = self._metric_queue.qsize()
                
                # Gestion du temps restant
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in metric processor: {e}")
                await asyncio.sleep(1)
    
    async def _transaction_processor(self) -> None:
        """Traite les transactions en batch."""
        while self._is_running:
            try:
                transactions = []
                start_time = time.time()
                
                # Collecte des transactions
                while len(transactions) < self.config["batch_size"]:
                    try:
                        transaction = await asyncio.wait_for(
                            self._transaction_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        transactions.append(transaction)
                    except asyncio.TimeoutError:
                        break
                
                # Envoi des transactions
                if transactions:
                    await self._send_transactions_batch(transactions)
                
                # Mise à jour des stats
                self._stats["queue_sizes"]["transactions"] = self._transaction_queue.qsize()
                
                # Gestion du temps restant
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in transaction processor: {e}")
                await asyncio.sleep(1)
    
    async def _send_events_batch(self, events: List[DynatraceEvent]) -> bool:
        """Envoie un batch d'événements."""
        try:
            url = f"{self.environment_url}/api/v2/events"
            payload = {
                "events": [event.to_dict() for event in events]
            }
            
            # Compression
            data = json.dumps(payload)
            if self.config["enable_compression"]:
                import gzip
                data = gzip.compress(data.encode())
                headers = {"Content-Encoding": "gzip"}
            else:
                headers = {}
            
            async with self._session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    self._stats["events_sent"] += len(events)
                    self._stats["last_event_time"] = datetime.now(timezone.utc).isoformat()
                    logger.debug(f"Sent {len(events)} events to Dynatrace")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Error sending events: {response.status} - {error_text}")
                    self._stats["events_failed"] += len(events)
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending events batch: {e}")
            self._stats["events_failed"] += len(events)
            return False
    
    async def _send_metrics_batch(self, metrics: List[DynatraceMetric]) -> bool:
        """Envoie un batch de métriques."""
        try:
            url = f"{self.environment_url}/api/v2/metrics/ingest"
            
            # Construction du payload au format Dynatrace
            lines = []
            for metric in metrics:
                line = f"{metric.name},{','.join([f'{k}={v}' for k, v in metric.dimensions.items()])} {metric.value} {int(metric.timestamp.timestamp() * 1000)}"
                lines.append(line)
            
            payload = "\n".join(lines)
            
            # Compression
            if self.config["enable_compression"]:
                import gzip
                payload = gzip.compress(payload.encode())
                headers = {"Content-Encoding": "gzip"}
            else:
                headers = {}
            
            async with self._session.post(url, data=payload, headers=headers) as response:
                if response.status in [200, 202]:
                    self._stats["metrics_sent"] += len(metrics)
                    self._stats["last_metric_time"] = datetime.now(timezone.utc).isoformat()
                    logger.debug(f"Sent {len(metrics)} metrics to Dynatrace")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Error sending metrics: {response.status} - {error_text}")
                    self._stats["metrics_failed"] += len(metrics)
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending metrics batch: {e}")
            self._stats["metrics_failed"] += len(metrics)
            return False
    
    async def _send_transactions_batch(self, transactions: List[DynatraceTransaction]) -> bool:
        """Envoie un batch de transactions."""
        try:
            url = f"{self.environment_url}/api/v2/transactions"
            payload = {
                "transactions": [transaction.to_dict() for transaction in transactions]
            }
            
            data = json.dumps(payload)
            if self.config["enable_compression"]:
                import gzip
                data = gzip.compress(data.encode())
                headers = {"Content-Encoding": "gzip"}
            else:
                headers = {}
            
            async with self._session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    self._stats["transactions_sent"] += len(transactions)
                    self._stats["last_transaction_time"] = datetime.now(timezone.utc).isoformat()
                    logger.debug(f"Sent {len(transactions)} transactions to Dynatrace")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Error sending transactions: {response.status} - {error_text}")
                    self._stats["transactions_failed"] += len(transactions)
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending transactions batch: {e}")
            self._stats["transactions_failed"] += len(transactions)
            return False
    
    # ========== MÉTHODES PRIVÉES - QUEUE ==========
    
    async def _queue_event(self, event: DynatraceEvent) -> bool:
        """Met un événement en queue."""
        try:
            await asyncio.wait_for(
                self._event_queue.put(event),
                timeout=5.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Event queue full, dropping event")
            self._stats["events_failed"] += 1
            return False
    
    async def _queue_metric(self, metric: DynatraceMetric) -> bool:
        """Met une métrique en queue."""
        try:
            await asyncio.wait_for(
                self._metric_queue.put(metric),
                timeout=5.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Metric queue full, dropping metric")
            self._stats["metrics_failed"] += 1
            return False
    
    async def _queue_transaction(self, transaction: DynatraceTransaction) -> bool:
        """Met une transaction en queue."""
        try:
            await asyncio.wait_for(
                self._transaction_queue.put(transaction),
                timeout=5.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Transaction queue full, dropping transaction")
            self._stats["transactions_failed"] += 1
            return False
    
    async def _flush_all_queues(self) -> None:
        """Vide toutes les queues."""
        # Événements
        events = []
        while not self._event_queue.empty():
            try:
                events.append(self._event_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if events:
            await self._send_events_batch(events)
        
        # Métriques
        metrics = []
        while not self._metric_queue.empty():
            try:
                metrics.append(self._metric_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if metrics:
            await self._send_metrics_batch(metrics)
        
        # Transactions
        transactions = []
        while not self._transaction_queue.empty():
            try:
                transactions.append(self._transaction_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if transactions:
            await self._send_transactions_batch(transactions)
    
    # ========== MÉTHODES PRIVÉES - ENRICHISSEMENT ==========
    
    async def _enrich_event(self, event: DynatraceEvent) -> None:
        """Enrichit un événement avec des métadonnées."""
        # Ajout de tags système
        event.tags.extend([
            "hedge_bot",
            f"env:{os.getenv('NEXUS_ENV', 'development')}",
            f"version:{os.getenv('NEXUS_VERSION', 'unknown')}"
        ])
        
        # Ajout de l'entité par défaut
        if not event.entity_id:
            event.entity_id = self._get_default_entity_id()
    
    async def _enrich_metric(self, metric: DynatraceMetric) -> None:
        """Enrichit une métrique avec des métadonnées."""
        # Ajout du préfixe
        if not metric.name.startswith(self.config["metrics"]["prefix"]):
            metric.name = f"{self.config['metrics']['prefix']}.{metric.name}"
        
        # Ajout de dimensions système
        metric.dimensions.update({
            "environment": os.getenv("NEXUS_ENV", "development"),
            "host": socket.gethostname(),
            "process": str(os.getpid())
        })
    
    async def _enrich_transaction(self, transaction: DynatraceTransaction) -> None:
        """Enrichit une transaction avec des métadonnées."""
        transaction.tags.extend([
            "hedge_bot",
            f"env:{os.getenv('NEXUS_ENV', 'development')}"
        ])
    
    def _get_default_entity_id(self) -> str:
        """Obtient l'ID de l'entité par défaut."""
        return f"HEDGE_BOT_{socket.gethostname()}_{os.getpid()}"
    
    # ========== MÉTHODES PRIVÉES - IMMÉDIATES ==========
    
    async def _send_event_immediate(self, event: DynatraceEvent) -> bool:
        """Envoie un événement immédiatement."""
        try:
            url = f"{self.environment_url}/api/v2/events"
            payload = {"events": [event.to_dict()]}
            
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    self._stats["events_sent"] += 1
                    self._stats["last_event_time"] = datetime.now(timezone.utc).isoformat()
                    return True
                else:
                    self._stats["events_failed"] += 1
                    return False
                    
        except Exception as e:
            self._stats["events_failed"] += 1
            logger.error(f"Error sending immediate event: {e}")
            return False
    
    async def _send_metric_immediate(self, metric: DynatraceMetric) -> bool:
        """Envoie une métrique immédiatement."""
        try:
            url = f"{self.environment_url}/api/v2/metrics/ingest"
            line = f"{metric.name},{','.join([f'{k}={v}' for k, v in metric.dimensions.items()])} {metric.value} {int(metric.timestamp.timestamp() * 1000)}"
            
            async with self._session.post(url, data=line) as response:
                if response.status in [200, 202]:
                    self._stats["metrics_sent"] += 1
                    self._stats["last_metric_time"] = datetime.now(timezone.utc).isoformat()
                    return True
                else:
                    self._stats["metrics_failed"] += 1
                    return False
                    
        except Exception as e:
            self._stats["metrics_failed"] += 1
            logger.error(f"Error sending immediate metric: {e}")
            return False
    
    async def _send_transaction_immediate(self, transaction: DynatraceTransaction) -> bool:
        """Envoie une transaction immédiatement."""
        try:
            url = f"{self.environment_url}/api/v2/transactions"
            payload = {"transactions": [transaction.to_dict()]}
            
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    self._stats["transactions_sent"] += 1
                    self._stats["last_transaction_time"] = datetime.now(timezone.utc).isoformat()
                    return True
                else:
                    self._stats["transactions_failed"] += 1
                    return False
                    
        except Exception as e:
            self._stats["transactions_failed"] += 1
            logger.error(f"Error sending immediate transaction: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - SYSTÈME ==========
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                is_healthy = await self._test_connection()
                self._health_status = "HEALTHY" if is_healthy else "UNHEALTHY"
                
                # Émission de l'état de santé
                if self.data_manager:
                    await self.data_manager.store(
                        f"dynatrace:health",
                        self._health_status,
                        DataType.METADATA
                    )
                
                logger.debug(f"Dynatrace health: {self._health_status}")
                
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                self._health_status = "ERROR"
    
    async def _system_metrics_loop(self) -> None:
        """Boucle de collecte des métriques système."""
        while self._is_running:
            await asyncio.sleep(self.config["system_metrics_interval"])
            
            try:
                # Métriques CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                
                # Métriques mémoire
                memory = psutil.virtual_memory()
                
                # Métriques disque
                disk = psutil.disk_usage('/')
                
                # Métriques réseau
                net = psutil.net_io_counters()
                
                # Création des métriques
                metrics = [
                    DynatraceMetric(
                        metric_id="system.cpu.usage",
                        name=f"{self.config['metrics']['prefix']}.system.cpu.usage",
                        value=cpu_percent,
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="%"
                    ),
                    DynatraceMetric(
                        metric_id="system.memory.usage",
                        name=f"{self.config['metrics']['prefix']}.system.memory.usage",
                        value=memory.percent,
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="%"
                    ),
                    DynatraceMetric(
                        metric_id="system.memory.available",
                        name=f"{self.config['metrics']['prefix']}.system.memory.available",
                        value=memory.available / (1024**2),
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="MB"
                    ),
                    DynatraceMetric(
                        metric_id="system.disk.usage",
                        name=f"{self.config['metrics']['prefix']}.system.disk.usage",
                        value=disk.percent,
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="%"
                    ),
                    DynatraceMetric(
                        metric_id="system.network.bytes_sent",
                        name=f"{self.config['metrics']['prefix']}.system.network.bytes_sent",
                        value=net.bytes_sent / (1024**2),
                        metric_type=DynatraceMetricType.COUNTER,
                        unit="MB"
                    ),
                    DynatraceMetric(
                        metric_id="system.network.bytes_recv",
                        name=f"{self.config['metrics']['prefix']}.system.network.bytes_recv",
                        value=net.bytes_recv / (1024**2),
                        metric_type=DynatraceMetricType.COUNTER,
                        unit="MB"
                    )
                ]
                
                # Ajout des métriques de processus
                process = psutil.Process()
                metrics.extend([
                    DynatraceMetric(
                        metric_id="process.cpu.usage",
                        name=f"{self.config['metrics']['prefix']}.process.cpu.usage",
                        value=process.cpu_percent(),
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="%"
                    ),
                    DynatraceMetric(
                        metric_id="process.memory.rss",
                        name=f"{self.config['metrics']['prefix']}.process.memory.rss",
                        value=process.memory_info().rss / (1024**2),
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="MB"
                    ),
                    DynatraceMetric(
                        metric_id="process.threads",
                        name=f"{self.config['metrics']['prefix']}.process.threads",
                        value=process.num_threads(),
                        metric_type=DynatraceMetricType.GAUGE,
                        unit="count"
                    )
                ])
                
                # Envoi des métriques
                for metric in metrics:
                    await self.send_metric(metric)
                
                # Stockage local
                self._system_metrics = {
                    "cpu": cpu_percent,
                    "memory": memory.percent,
                    "disk": disk.percent,
                    "process_cpu": process.cpu_percent(),
                    "process_memory": process.memory_info().rss / (1024**2)
                }
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
    
    async def _entity_management_loop(self) -> None:
        """Boucle de gestion des entités."""
        if not self.config["entities"]["auto_create"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["entities"]["update_interval"])
            
            try:
                # Création/mise à jour des entités
                await self._update_entities()
                
            except Exception as e:
                logger.error(f"Error in entity management: {e}")
    
    async def _update_entities(self) -> None:
        """Met à jour les entités dans Dynatrace."""
        # Entité Hedge Bot
        hedge_bot_entity = DynatraceEntity(
            entity_id=f"HEDGE_BOT_{socket.gethostname()}",
            entity_type=DynatraceEntityType.HEDGE_BOT,
            display_name=f"Hedge Bot {socket.gethostname()}",
            tags=["hedge_bot", "trading", "production"],
            properties={
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "python_version": platform.python_version(),
                "started_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Envoi de l'entité (via un événement spécial)
        event = DynatraceEvent(
            event_type=DynatraceEventType.CUSTOM,
            severity=DynatraceSeverity.INFO,
            title="Entity Update",
            message=f"Updating entity {hedge_bot_entity.display_name}",
            source="DynatraceIntegration",
            tags=["entity", "update"],
            properties=hedge_bot_entity.to_dict()
        )
        await self.send_event(event)
    
    async def _auto_discover_entities(self) -> None:
        """Auto-découverte des entités existantes."""
        try:
            entities = await self.get_entities(f"type({DynatraceEntityType.HEDGE_BOT.value})")
            
            for entity in entities:
                self._entity_cache[entity.entity_id] = entity
                
            logger.info(f"Auto-discovered {len(entities)} entities")
            
        except Exception as e:
            logger.error(f"Error in auto-discovery: {e}")
    
    async def _test_connection(self) -> bool:
        """Teste la connexion à Dynatrace."""
        try:
            url = f"{self.environment_url}/api/v2/metrics/query"
            params = {
                "metricSelector": "builtin:service.response.time:avg",
                "from": "now-1m",
                "to": "now"
            }
            
            async with self._session.get(url, params=params) as response:
                return response.status == 200
                
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - PARSING ==========
    
    def _parse_metrics_response(self, data: Dict) -> List[DynatraceMetric]:
        """Parse la réponse de l'API metrics."""
        metrics = []
        
        try:
            for result in data.get("result", []):
                metric_id = result.get("metricId", "")
                data_points = result.get("data", [])
                
                for point in data_points:
                    for dimension_values in point.get("dimensions", [[]]):
                        dimensions = {}
                        if len(dimension_values) > 0:
                            dim_names = result.get("dimensionDefinitions", {})
                            for idx, value in enumerate(dimension_values):
                                dim_name = list(dim_names.keys())[idx] if idx < len(dim_names) else f"dim{idx}"
                                dimensions[dim_name] = value
                        
                        values = point.get("values", [])
                        for i, value in enumerate(values):
                            if value is not None:
                                timestamp = point.get("timestamps", [])[i] if i < len(point.get("timestamps", [])) else int(time.time() * 1000)
                                metric = DynatraceMetric(
                                    metric_id=f"{metric_id}_{i}",
                                    name=metric_id,
                                    value=float(value),
                                    timestamp=datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                                    dimensions=dimensions
                                )
                                metrics.append(metric)
                                
        except Exception as e:
            logger.error(f"Error parsing metrics response: {e}")
        
        return metrics
    
    def _parse_entities_response(self, data: Dict) -> List[DynatraceEntity]:
        """Parse la réponse de l'API entities."""
        entities = []
        
        try:
            for entity_data in data.get("entities", []):
                entity = DynatraceEntity(
                    entity_id=entity_data.get("entityId", str(uuid.uuid4())),
                    entity_type=DynatraceEntityType(entity_data.get("type", "CUSTOM")),
                    display_name=entity_data.get("displayName", ""),
                    tags=entity_data.get("tags", []),
                    properties=entity_data.get("properties", {}),
                    health_status=entity_data.get("healthStatus", "OK")
                )
                entities.append(entity)
                
        except Exception as e:
            logger.error(f"Error parsing entities response: {e}")
        
        return entities
    
    # ========== MÉTHODES PUBLIQUES - STATS ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        return self._stats
    
    def get_health(self) -> str:
        """Récupère l'état de santé."""
        return self._health_status
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques système."""
        return self._system_metrics


# ============== CONTEXT MANAGER ==============

class DynatraceTransactionContext:
    """Context manager pour les transactions Dynatrace."""
    
    def __init__(
        self,
        integration: DynatraceIntegration,
        name: str,
        service: str = "",
        method: str = "",
        url: str = "",
        **kwargs
    ):
        self.integration = integration
        self.name = name
        self.service = service
        self.method = method
        self.url = url
        self.kwargs = kwargs
        
        self.transaction = DynatraceTransaction(
            name=name,
            service=service,
            method=method,
            url=url,
            properties=kwargs
        )
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = datetime.now(timezone.utc)
        self.transaction.start_time = self.start_time
        return self.transaction
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now(timezone.utc)
        self.transaction.end_time = end_time
        self.transaction.duration = (end_time - self.start_time).total_seconds()
        self.transaction.success = exc_type is None
        if exc_val:
            self.transaction.properties["error"] = str(exc_val)
        
        await self.integration.send_transaction(self.transaction)


# ============== FACTORY ==============

class DynatraceIntegrationFactory:
    """Factory pour créer des intégrations Dynatrace."""
    
    @staticmethod
    async def create_integration(
        api_token: str,
        environment_url: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> DynatraceIntegration:
        """Crée une intégration Dynatrace."""
        integration = DynatraceIntegration(
            api_token=api_token,
            environment_url=environment_url,
            data_manager=data_manager,
            config=config
        )
        await integration.start()
        return integration


# ============== EXPORT ==============

__all__ = [
    "DynatraceEventType",
    "DynatraceSeverity",
    "DynatraceMetricType",
    "DynatraceEntityType",
    "DynatraceEvent",
    "DynatraceMetric",
    "DynatraceEntity",
    "DynatraceTransaction",
    "DynatraceIntegration",
    "DynatraceTransactionContext",
    "DynatraceIntegrationFactory"
]
