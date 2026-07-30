# trading/bots/hedge_bot/hedge_bot_data_elk.py
# Advanced ELK Stack Integration for Hedge Bot - Logging, Monitoring & Analytics
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot ELK Stack Integration - Module d'intégration avancé avec ELK Stack (Elasticsearch, Logstash, Kibana)
pour le Hedge Bot. Assure une gestion centralisée des logs, une analyse en temps réel, des tableaux de bord
interactifs et des alertes intelligentes pour l'ensemble du système de hedging.
"""

import asyncio
import json
import time
import hashlib
import socket
import os
import platform
import traceback
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
import gzip
from elasticsearch import AsyncElasticsearch, exceptions as es_exceptions
from elasticsearch.helpers import async_bulk

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_elk")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class ElkLogLevel(Enum):
    """Niveaux de log ELK."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class ElkIndexType(Enum):
    """Types d'index ELK."""
    LOGS = "logs"
    METRICS = "metrics"
    EVENTS = "events"
    TRANSACTIONS = "transactions"
    DECISIONS = "decisions"
    TRADES = "trades"
    POSITIONS = "positions"
    RISK = "risk"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    ALERTS = "alerts"


class ElkAlertSeverity(Enum):
    """Sévérité des alertes ELK."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ElkDataRetention(Enum):
    """Politiques de rétention des données ELK."""
    DAYS_7 = 7
    DAYS_30 = 30
    DAYS_90 = 90
    DAYS_180 = 180
    DAYS_365 = 365
    FOREVER = -1


# ============== DATA MODELS ==============

@dataclass
class ElkLogEntry:
    """Modèle d'entrée de log ELK."""
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    level: ElkLogLevel = ElkLogLevel.INFO
    message: str = ""
    source: str = ""
    module: str = ""
    function: str = ""
    line: int = 0
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    environment: str = os.getenv("NEXUS_ENV", "development")
    host: str = socket.gethostname()
    service: str = "hedge_bot"
    version: str = os.getenv("NEXUS_VERSION", "unknown")
    
    def to_elasticsearch(self) -> Dict:
        """Convertit en document Elasticsearch."""
        return {
            "log_id": self.log_id,
            "@timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
            "module": self.module,
            "function": self.function,
            "line": self.line,
            "traceback": self.traceback,
            "context": self.context,
            "tags": self.tags,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "environment": self.environment,
            "host": self.host,
            "service": self.service,
            "version": self.version
        }


@dataclass
class ElkMetric:
    """Modèle de métrique ELK."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    type: str = "gauge"  # gauge, counter, histogram, summary
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_elasticsearch(self) -> Dict:
        """Convertit en document Elasticsearch."""
        return {
            "metric_id": self.metric_id,
            "@timestamp": self.timestamp.isoformat(),
            "name": self.name,
            "value": self.value,
            "dimensions": self.dimensions,
            "unit": self.unit,
            "type": self.type,
            "tags": self.tags,
            "metadata": self.metadata
        }


@dataclass
class ElkEvent:
    """Modèle d'événement ELK."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    title: str = ""
    description: str = ""
    severity: ElkAlertSeverity = ElkAlertSeverity.MEDIUM
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: str = ""
    
    def to_elasticsearch(self) -> Dict:
        """Convertit en document Elasticsearch."""
        return {
            "event_id": self.event_id,
            "@timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "source": self.source,
            "data": self.data,
            "tags": self.tags,
            "correlation_id": self.correlation_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type
        }


@dataclass
class ElkAlert:
    """Modèle d'alerte ELK."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    severity: ElkAlertSeverity = ElkAlertSeverity.MEDIUM
    condition: str = ""
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    status: str = "active"  # active, resolved, acknowledged
    value: float = 0.0
    threshold: float = 0.0
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    notification_sent: bool = False
    
    def to_elasticsearch(self) -> Dict:
        """Convertit en document Elasticsearch."""
        return {
            "alert_id": self.alert_id,
            "@timestamp": self.triggered_at.isoformat(),
            "name": self.name,
            "severity": self.severity.value,
            "condition": self.condition,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
            "context": self.context,
            "tags": self.tags,
            "notification_sent": self.notification_sent
        }


# ============== INTERFACES ==============

class ElkIntegrationInterface:
    """Interface abstraite pour l'intégration ELK."""
    
    @abstractmethod
    async def log(self, entry: ElkLogEntry) -> bool:
        """Envoie un log à ELK."""
        pass
    
    @abstractmethod
    async def send_metric(self, metric: ElkMetric) -> bool:
        """Envoie une métrique à ELK."""
        pass
    
    @abstractmethod
    async def send_event(self, event: ElkEvent) -> bool:
        """Envoie un événement à ELK."""
        pass
    
    @abstractmethod
    async def send_alert(self, alert: ElkAlert) -> bool:
        """Envoie une alerte à ELK."""
        pass
    
    @abstractmethod
    async def search(self, index: str, query: Dict) -> List[Dict]:
        """Recherche dans ELK."""
        pass


# ============== IMPLÉMENTATION ==============

class ElkIntegration(ElkIntegrationInterface):
    """
    Intégration avancée avec ELK Stack pour le Hedge Bot.
    Gère les logs centralisés, les métriques, les événements, les alertes et les analyses.
    """
    
    def __init__(
        self,
        hosts: List[str],
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        ssl_verify: bool = True
    ):
        self.hosts = hosts
        self.username = username
        self.password = password
        self.api_key = api_key
        self.ssl_verify = ssl_verify
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Client Elasticsearch
        self._es: Optional[AsyncElasticsearch] = None
        
        # Queues
        self._log_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._metric_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._alert_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Cache
        self._index_cache: Dict[str, str] = {}
        self._alert_cache: Dict[str, ElkAlert] = {}
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "logs_sent": 0,
            "metrics_sent": 0,
            "events_sent": 0,
            "alerts_sent": 0,
            "logs_failed": 0,
            "metrics_failed": 0,
            "events_failed": 0,
            "alerts_failed": 0,
            "queue_sizes": {
                "logs": 0,
                "metrics": 0,
                "events": 0,
                "alerts": 0
            }
        }
        
        # État
        self._is_running = False
        self._health_status = "UNKNOWN"
        
        # Thread pools
        self._io_executor = ThreadPoolExecutor(max_workers=10)
        
        logger.info("ElkIntegration initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "batch_size": 100,
            "flush_interval": 5,
            "retry_count": 3,
            "retry_delay": 1.0,
            "timeout": 30.0,
            "max_queue_size": 10000,
            "enable_compression": True,
            "index_prefix": "nexus_hedge_bot",
            "index_settings": {
                "number_of_shards": 2,
                "number_of_replicas": 1
            },
            "rotation": {
                "enabled": True,
                "interval": "daily",  # daily, weekly, monthly
                "max_size": "50gb"
            },
            "retention": {
                "logs": ElkDataRetention.DAYS_30,
                "metrics": ElkDataRetention.DAYS_90,
                "events": ElkDataRetention.DAYS_180,
                "alerts": ElkDataRetention.DAYS_365,
                "audit": ElkDataRetention.DAYS_365
            },
            "alerts": {
                "enabled": True,
                "check_interval": 60,
                "notification": {
                    "enabled": True,
                    "channels": ["slack", "email", "webhook"]
                }
            },
            "analytics": {
                "enabled": True,
                "auto_index": True,
                "aggregation_interval": 60
            }
        }
    
    async def start(self) -> None:
        """Démarre l'intégration ELK."""
        logger.info("ElkIntegration starting...")
        
        self._is_running = True
        
        # Initialisation du client Elasticsearch
        self._es = AsyncElasticsearch(
            hosts=self.hosts,
            http_auth=(self.username, self.password) if self.username and self.password else None,
            api_key=self.api_key,
            verify_certs=self.ssl_verify,
            timeout=self.config["timeout"],
            retry_on_timeout=True,
            max_retries=self.config["retry_count"]
        )
        
        # Vérification de la connexion
        if await self._test_connection():
            self._health_status = "HEALTHY"
            logger.info("Connected to Elasticsearch")
        else:
            self._health_status = "UNHEALTHY"
            logger.warning("Failed to connect to Elasticsearch")
        
        # Création des index
        await self._create_indices()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._log_processor())
        asyncio.create_task(self._metric_processor())
        asyncio.create_task(self._event_processor())
        asyncio.create_task(self._alert_processor())
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._index_rotation_loop())
        asyncio.create_task(self._alert_check_loop())
        asyncio.create_task(self._analytics_loop())
        
        logger.info("ElkIntegration started")
    
    async def stop(self) -> None:
        """Arrête l'intégration ELK."""
        logger.info("ElkIntegration stopping...")
        
        self._is_running = False
        
        # Vidage des queues
        await self._flush_all_queues()
        
        # Fermeture du client
        if self._es:
            await self._es.close()
        
        self._io_executor.shutdown(wait=True)
        logger.info("ElkIntegration stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def log(self, entry: ElkLogEntry) -> bool:
        """Envoie un log à ELK."""
        if not self._is_running:
            logger.warning("ElkIntegration not running, log queued")
            return await self._queue_log(entry)
        
        try:
            # Enrichissement du log
            await self._enrich_log(entry)
            
            # Mise en queue
            if self.config["batch_size"] > 1:
                return await self._queue_log(entry)
            else:
                return await self._send_log_immediate(entry)
            
        except Exception as e:
            self._stats["logs_failed"] += 1
            logger.error(f"Error sending log: {e}")
            return False
    
    async def send_metric(self, metric: ElkMetric) -> bool:
        """Envoie une métrique à ELK."""
        if not self._is_running:
            logger.warning("ElkIntegration not running, metric queued")
            return await self._queue_metric(metric)
        
        try:
            # Enrichissement de la métrique
            await self._enrich_metric(metric)
            
            # Mise en queue
            if self.config["batch_size"] > 1:
                return await self._queue_metric(metric)
            else:
                return await self._send_metric_immediate(metric)
            
        except Exception as e:
            self._stats["metrics_failed"] += 1
            logger.error(f"Error sending metric: {e}")
            return False
    
    async def send_event(self, event: ElkEvent) -> bool:
        """Envoie un événement à ELK."""
        if not self._is_running:
            logger.warning("ElkIntegration not running, event queued")
            return await self._queue_event(event)
        
        try:
            # Enrichissement de l'événement
            await self._enrich_event(event)
            
            # Mise en queue
            if self.config["batch_size"] > 1:
                return await self._queue_event(event)
            else:
                return await self._send_event_immediate(event)
            
        except Exception as e:
            self._stats["events_failed"] += 1
            logger.error(f"Error sending event: {e}")
            return False
    
    async def send_alert(self, alert: ElkAlert) -> bool:
        """Envoie une alerte à ELK."""
        if not self._is_running:
            logger.warning("ElkIntegration not running, alert queued")
            return await self._queue_alert(alert)
        
        try:
            # Enrichissement de l'alerte
            await self._enrich_alert(alert)
            
            # Mise en cache
            self._alert_cache[alert.alert_id] = alert
            
            # Mise en queue
            if self.config["batch_size"] > 1:
                return await self._queue_alert(alert)
            else:
                return await self._send_alert_immediate(alert)
            
        except Exception as e:
            self._stats["alerts_failed"] += 1
            logger.error(f"Error sending alert: {e}")
            return False
    
    async def search(self, index: str, query: Dict) -> List[Dict]:
        """Recherche dans ELK."""
        try:
            response = await self._es.search(index=index, body=query)
            hits = response.get("hits", {}).get("hits", [])
            return [hit.get("_source", {}) for hit in hits]
            
        except Exception as e:
            logger.error(f"Error searching ELK: {e}")
            return []
    
    # ========== MÉTHODES SPÉCIFIQUES HEDGE BOT ==========
    
    async def log_decision(self, decision: Decision) -> None:
        """Log une décision de hedging."""
        entry = ElkLogEntry(
            level=ElkLogLevel.INFO,
            message=f"Hedge Decision: {decision.decision_type.value}",
            source="HedgeDecisionEngine",
            module="hedge_bot.decision",
            context={
                "decision_id": decision.decision_id,
                "decision_type": decision.decision_type.value,
                "confidence": decision.confidence,
                "strategy": decision.strategy.value,
                "target_asset": decision.target_asset,
                "target_amount": decision.target_amount,
                "target_price": decision.target_price,
                "reason": decision.reason
            },
            tags=["hedge", "decision", decision.decision_type.value],
            correlation_id=decision.decision_id
        )
        await self.log(entry)
        
        # Événement associé
        event = ElkEvent(
            event_type="hedge_decision",
            title=f"Hedge Decision: {decision.decision_type.value}",
            description=f"Decision made with confidence {decision.confidence:.2f}",
            severity=ElkAlertSeverity.MEDIUM,
            data=decision.to_dict(),
            tags=["hedge", "decision"],
            correlation_id=decision.decision_id
        )
        await self.send_event(event)
    
    async def log_decision_result(self, result: DecisionResult) -> None:
        """Log le résultat d'une décision de hedging."""
        level = ElkLogLevel.INFO if result.executed else ElkLogLevel.ERROR
        
        entry = ElkLogEntry(
            level=level,
            message=f"Hedge Decision Result: {result.decision.decision_type.value} - {'Success' if result.executed else 'Failed'}",
            source="HedgeDecisionEngine",
            module="hedge_bot.decision",
            context={
                "decision_id": result.decision.decision_id,
                "executed": result.executed,
                "execution_time": result.execution_time,
                "error": result.error,
                "result_data": result.result_data
            },
            tags=["hedge", "decision", "result"],
            correlation_id=result.decision.decision_id
        )
        await self.log(entry)
        
        # Métrique de performance
        metric = ElkMetric(
            name="hedge.decision.execution_time",
            value=result.execution_time,
            dimensions={
                "decision_type": result.decision.decision_type.value,
                "executed": str(result.executed)
            },
            unit="seconds",
            type="histogram"
        )
        await self.send_metric(metric)
    
    async def log_trade(self, trade: Dict[str, Any]) -> None:
        """Log une transaction de trading."""
        entry = ElkLogEntry(
            level=ElkLogLevel.INFO,
            message=f"Trade Executed: {trade.get('symbol', 'unknown')}",
            source="ExecutionEngine",
            module="hedge_bot.execution",
            context=trade,
            tags=["trade", trade.get('side', '')],
            correlation_id=trade.get('trade_id')
        )
        await self.log(entry)
        
        # Événement de trade
        event = ElkEvent(
            event_type="trade_executed",
            title=f"Trade: {trade.get('symbol', 'unknown')}",
            description=f"{trade.get('side', '')} {trade.get('amount', 0)} at {trade.get('price', 0)}",
            severity=ElkAlertSeverity.LOW,
            data=trade,
            tags=["trade"],
            correlation_id=trade.get('trade_id')
        )
        await self.send_event(event)
        
        # Métriques de trading
        metric = ElkMetric(
            name="hedge.trade.volume",
            value=float(trade.get("amount", 0)),
            dimensions={
                "symbol": trade.get("symbol", "unknown"),
                "side": trade.get("side", "unknown")
            },
            unit="units",
            type="counter"
        )
        await self.send_metric(metric)
    
    async def log_risk_metrics(self, risk_metrics: Dict[str, Any]) -> None:
        """Log les métriques de risque."""
        risk_score = risk_metrics.get("risk_score", 0.0)
        risk_level = risk_metrics.get("risk_level", "low")
        
        level = ElkLogLevel.INFO
        if risk_level == "high":
            level = ElkLogLevel.WARNING
        elif risk_level == "critical":
            level = ElkLogLevel.ERROR
        
        entry = ElkLogEntry(
            level=level,
            message=f"Risk Metrics: {risk_level.upper()} - Score: {risk_score:.2f}",
            source="RiskEngine",
            module="hedge_bot.risk",
            context=risk_metrics,
            tags=["risk", risk_level]
        )
        await self.log(entry)
        
        # Événement de risque
        severity = ElkAlertSeverity.MEDIUM
        if risk_level == "high":
            severity = ElkAlertSeverity.HIGH
        elif risk_level == "critical":
            severity = ElkAlertSeverity.CRITICAL
        
        event = ElkEvent(
            event_type="risk_update",
            title=f"Risk Level: {risk_level.upper()}",
            description=f"Risk score: {risk_score:.2f}",
            severity=severity,
            data=risk_metrics,
            tags=["risk"]
        )
        await self.send_event(event)
        
        # Métriques de risque
        for key, value in risk_metrics.items():
            if isinstance(value, (int, float)):
                metric = ElkMetric(
                    name=f"hedge.risk.{key}",
                    value=float(value),
                    type="gauge",
                    unit=""
                )
                await self.send_metric(metric)
    
    async def log_performance(self, performance: Dict[str, Any]) -> None:
        """Log les métriques de performance."""
        entry = ElkLogEntry(
            level=ElkLogLevel.INFO,
            message=f"Performance: PnL {performance.get('pnl', 0.0):.2f}",
            source="PerformanceMonitor",
            module="hedge_bot.performance",
            context=performance,
            tags=["performance"]
        )
        await self.log(entry)
        
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
                metric = ElkMetric(
                    name=key,
                    value=float(value),
                    type="gauge",
                    unit=""
                )
                await self.send_metric(metric)
    
    # ========== MÉTHODES PRIVÉES - PROCESSING ==========
    
    async def _log_processor(self) -> None:
        """Traite les logs en batch."""
        while self._is_running:
            try:
                logs = []
                start_time = time.time()
                
                while len(logs) < self.config["batch_size"]:
                    try:
                        log_entry = await asyncio.wait_for(
                            self._log_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        logs.append(log_entry)
                    except asyncio.TimeoutError:
                        break
                
                if logs:
                    await self._send_logs_batch(logs)
                
                self._stats["queue_sizes"]["logs"] = self._log_queue.qsize()
                
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in log processor: {e}")
                await asyncio.sleep(1)
    
    async def _metric_processor(self) -> None:
        """Traite les métriques en batch."""
        while self._is_running:
            try:
                metrics = []
                start_time = time.time()
                
                while len(metrics) < self.config["batch_size"]:
                    try:
                        metric = await asyncio.wait_for(
                            self._metric_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        metrics.append(metric)
                    except asyncio.TimeoutError:
                        break
                
                if metrics:
                    await self._send_metrics_batch(metrics)
                
                self._stats["queue_sizes"]["metrics"] = self._metric_queue.qsize()
                
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in metric processor: {e}")
                await asyncio.sleep(1)
    
    async def _event_processor(self) -> None:
        """Traite les événements en batch."""
        while self._is_running:
            try:
                events = []
                start_time = time.time()
                
                while len(events) < self.config["batch_size"]:
                    try:
                        event = await asyncio.wait_for(
                            self._event_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        events.append(event)
                    except asyncio.TimeoutError:
                        break
                
                if events:
                    await self._send_events_batch(events)
                
                self._stats["queue_sizes"]["events"] = self._event_queue.qsize()
                
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
                await asyncio.sleep(1)
    
    async def _alert_processor(self) -> None:
        """Traite les alertes en batch."""
        while self._is_running:
            try:
                alerts = []
                start_time = time.time()
                
                while len(alerts) < self.config["batch_size"]:
                    try:
                        alert = await asyncio.wait_for(
                            self._alert_queue.get(),
                            timeout=self.config["flush_interval"]
                        )
                        alerts.append(alert)
                    except asyncio.TimeoutError:
                        break
                
                if alerts:
                    await self._send_alerts_batch(alerts)
                
                self._stats["queue_sizes"]["alerts"] = self._alert_queue.qsize()
                
                elapsed = time.time() - start_time
                if elapsed < self.config["flush_interval"]:
                    await asyncio.sleep(self.config["flush_interval"] - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in alert processor: {e}")
                await asyncio.sleep(1)
    
    # ========== MÉTHODES PRIVÉES - ENVOI BATCH ==========
    
    async def _send_logs_batch(self, logs: List[ElkLogEntry]) -> bool:
        """Envoie un batch de logs."""
        try:
            index = self._get_index_name(ElkIndexType.LOGS)
            documents = [
                {
                    "_index": index,
                    "_source": log.to_elasticsearch()
                }
                for log in logs
            ]
            
            success, failed = await async_bulk(self._es, documents)
            
            if failed:
                self._stats["logs_failed"] += failed
                logger.error(f"Failed to send {failed} logs to ELK")
                return False
            
            self._stats["logs_sent"] += success
            logger.debug(f"Sent {success} logs to ELK")
            return True
            
        except Exception as e:
            self._stats["logs_failed"] += len(logs)
            logger.error(f"Error sending logs batch: {e}")
            return False
    
    async def _send_metrics_batch(self, metrics: List[ElkMetric]) -> bool:
        """Envoie un batch de métriques."""
        try:
            index = self._get_index_name(ElkIndexType.METRICS)
            documents = [
                {
                    "_index": index,
                    "_source": metric.to_elasticsearch()
                }
                for metric in metrics
            ]
            
            success, failed = await async_bulk(self._es, documents)
            
            if failed:
                self._stats["metrics_failed"] += failed
                logger.error(f"Failed to send {failed} metrics to ELK")
                return False
            
            self._stats["metrics_sent"] += success
            logger.debug(f"Sent {success} metrics to ELK")
            return True
            
        except Exception as e:
            self._stats["metrics_failed"] += len(metrics)
            logger.error(f"Error sending metrics batch: {e}")
            return False
    
    async def _send_events_batch(self, events: List[ElkEvent]) -> bool:
        """Envoie un batch d'événements."""
        try:
            index = self._get_index_name(ElkIndexType.EVENTS)
            documents = [
                {
                    "_index": index,
                    "_source": event.to_elasticsearch()
                }
                for event in events
            ]
            
            success, failed = await async_bulk(self._es, documents)
            
            if failed:
                self._stats["events_failed"] += failed
                logger.error(f"Failed to send {failed} events to ELK")
                return False
            
            self._stats["events_sent"] += success
            logger.debug(f"Sent {success} events to ELK")
            return True
            
        except Exception as e:
            self._stats["events_failed"] += len(events)
            logger.error(f"Error sending events batch: {e}")
            return False
    
    async def _send_alerts_batch(self, alerts: List[ElkAlert]) -> bool:
        """Envoie un batch d'alertes."""
        try:
            index = self._get_index_name(ElkIndexType.ALERTS)
            documents = [
                {
                    "_index": index,
                    "_source": alert.to_elasticsearch()
                }
                for alert in alerts
            ]
            
            success, failed = await async_bulk(self._es, documents)
            
            if failed:
                self._stats["alerts_failed"] += failed
                logger.error(f"Failed to send {failed} alerts to ELK")
                return False
            
            self._stats["alerts_sent"] += success
            logger.debug(f"Sent {success} alerts to ELK")
            return True
            
        except Exception as e:
            self._stats["alerts_failed"] += len(alerts)
            logger.error(f"Error sending alerts batch: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - IMMÉDIAT ==========
    
    async def _send_log_immediate(self, log_entry: ElkLogEntry) -> bool:
        """Envoie un log immédiatement."""
        try:
            index = self._get_index_name(ElkIndexType.LOGS)
            response = await self._es.index(index=index, document=log_entry.to_elasticsearch())
            
            if response.get("result") in ["created", "updated"]:
                self._stats["logs_sent"] += 1
                return True
            else:
                self._stats["logs_failed"] += 1
                return False
                
        except Exception as e:
            self._stats["logs_failed"] += 1
            logger.error(f"Error sending immediate log: {e}")
            return False
    
    async def _send_metric_immediate(self, metric: ElkMetric) -> bool:
        """Envoie une métrique immédiatement."""
        try:
            index = self._get_index_name(ElkIndexType.METRICS)
            response = await self._es.index(index=index, document=metric.to_elasticsearch())
            
            if response.get("result") in ["created", "updated"]:
                self._stats["metrics_sent"] += 1
                return True
            else:
                self._stats["metrics_failed"] += 1
                return False
                
        except Exception as e:
            self._stats["metrics_failed"] += 1
            logger.error(f"Error sending immediate metric: {e}")
            return False
    
    async def _send_event_immediate(self, event: ElkEvent) -> bool:
        """Envoie un événement immédiatement."""
        try:
            index = self._get_index_name(ElkIndexType.EVENTS)
            response = await self._es.index(index=index, document=event.to_elasticsearch())
            
            if response.get("result") in ["created", "updated"]:
                self._stats["events_sent"] += 1
                return True
            else:
                self._stats["events_failed"] += 1
                return False
                
        except Exception as e:
            self._stats["events_failed"] += 1
            logger.error(f"Error sending immediate event: {e}")
            return False
    
    async def _send_alert_immediate(self, alert: ElkAlert) -> bool:
        """Envoie une alerte immédiatement."""
        try:
            index = self._get_index_name(ElkIndexType.ALERTS)
            response = await self._es.index(index=index, document=alert.to_elasticsearch())
            
            if response.get("result") in ["created", "updated"]:
                self._stats["alerts_sent"] += 1
                return True
            else:
                self._stats["alerts_failed"] += 1
                return False
                
        except Exception as e:
            self._stats["alerts_failed"] += 1
            logger.error(f"Error sending immediate alert: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - QUEUE ==========
    
    async def _queue_log(self, log_entry: ElkLogEntry) -> bool:
        """Met un log en queue."""
        try:
            await asyncio.wait_for(
                self._log_queue.put(log_entry),
                timeout=5.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Log queue full, dropping log")
            self._stats["logs_failed"] += 1
            return False
    
    async def _queue_metric(self, metric: ElkMetric) -> bool:
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
    
    async def _queue_event(self, event: ElkEvent) -> bool:
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
    
    async def _queue_alert(self, alert: ElkAlert) -> bool:
        """Met une alerte en queue."""
        try:
            await asyncio.wait_for(
                self._alert_queue.put(alert),
                timeout=5.0
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Alert queue full, dropping alert")
            self._stats["alerts_failed"] += 1
            return False
    
    async def _flush_all_queues(self) -> None:
        """Vide toutes les queues."""
        # Logs
        logs = []
        while not self._log_queue.empty():
            try:
                logs.append(self._log_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if logs:
            await self._send_logs_batch(logs)
        
        # Métriques
        metrics = []
        while not self._metric_queue.empty():
            try:
                metrics.append(self._metric_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if metrics:
            await self._send_metrics_batch(metrics)
        
        # Événements
        events = []
        while not self._event_queue.empty():
            try:
                events.append(self._event_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if events:
            await self._send_events_batch(events)
        
        # Alertes
        alerts = []
        while not self._alert_queue.empty():
            try:
                alerts.append(self._alert_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        
        if alerts:
            await self._send_alerts_batch(alerts)
    
    # ========== MÉTHODES PRIVÉES - ENRICHISSEMENT ==========
    
    async def _enrich_log(self, entry: ElkLogEntry) -> None:
        """Enrichit un log avec des métadonnées."""
        entry.environment = os.getenv("NEXUS_ENV", "development")
        entry.host = socket.gethostname()
        entry.service = "hedge_bot"
        entry.version = os.getenv("NEXUS_VERSION", "unknown")
        
        if not entry.correlation_id:
            entry.correlation_id = str(uuid.uuid4())
    
    async def _enrich_metric(self, metric: ElkMetric) -> None:
        """Enrichit une métrique avec des métadonnées."""
        metric.dimensions.update({
            "environment": os.getenv("NEXUS_ENV", "development"),
            "host": socket.gethostname(),
            "service": "hedge_bot"
        })
    
    async def _enrich_event(self, event: ElkEvent) -> None:
        """Enrichit un événement avec des métadonnées."""
        event.tags.extend([
            "hedge_bot",
            f"env:{os.getenv('NEXUS_ENV', 'development')}"
        ])
    
    async def _enrich_alert(self, alert: ElkAlert) -> None:
        """Enrichit une alerte avec des métadonnées."""
        alert.tags.extend([
            "hedge_bot",
            f"env:{os.getenv('NEXUS_ENV', 'development')}"
        ])
    
    # ========== MÉTHODES PRIVÉES - INDEX ==========
    
    def _get_index_name(self, index_type: ElkIndexType) -> str:
        """Obtient le nom de l'index pour un type."""
        prefix = self.config["index_prefix"]
        
        if self.config["rotation"]["enabled"]:
            now = datetime.now(timezone.utc)
            interval = self.config["rotation"]["interval"]
            
            if interval == "daily":
                suffix = now.strftime("%Y.%m.%d")
            elif interval == "weekly":
                suffix = now.strftime("%Y.%W")
            elif interval == "monthly":
                suffix = now.strftime("%Y.%m")
            else:
                suffix = now.strftime("%Y.%m.%d")
        else:
            suffix = "v1"
        
        return f"{prefix}_{index_type.value}_{suffix}"
    
    async def _create_indices(self) -> None:
        """Crée les index Elasticsearch."""
        for index_type in ElkIndexType:
            index_name = self._get_index_name(index_type)
            
            try:
                if not await self._es.indices.exists(index=index_name):
                    # Création de l'index avec mapping
                    mapping = self._get_index_mapping(index_type)
                    settings = self.config["index_settings"]
                    
                    await self._es.indices.create(
                        index=index_name,
                        mappings=mapping,
                        settings=settings
                    )
                    logger.info(f"Created index: {index_name}")
                    
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {e}")
    
    def _get_index_mapping(self, index_type: ElkIndexType) -> Dict:
        """Obtient le mapping Elasticsearch pour un type d'index."""
        base_mapping = {
            "properties": {
                "@timestamp": {"type": "date"},
                "environment": {"type": "keyword"},
                "host": {"type": "keyword"},
                "service": {"type": "keyword"},
                "version": {"type": "keyword"},
                "tags": {"type": "keyword"}
            }
        }
        
        if index_type == ElkIndexType.LOGS:
            base_mapping["properties"].update({
                "log_id": {"type": "keyword"},
                "level": {"type": "keyword"},
                "message": {"type": "text"},
                "source": {"type": "keyword"},
                "module": {"type": "keyword"},
                "function": {"type": "keyword"},
                "line": {"type": "integer"},
                "traceback": {"type": "text"},
                "context": {"type": "object", "enabled": True},
                "correlation_id": {"type": "keyword"},
                "session_id": {"type": "keyword"},
                "user_id": {"type": "keyword"}
            })
        
        elif index_type == ElkIndexType.METRICS:
            base_mapping["properties"].update({
                "metric_id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "value": {"type": "float"},
                "dimensions": {"type": "object", "enabled": True},
                "unit": {"type": "keyword"},
                "type": {"type": "keyword"}
            })
        
        elif index_type == ElkIndexType.EVENTS:
            base_mapping["properties"].update({
                "event_id": {"type": "keyword"},
                "event_type": {"type": "keyword"},
                "title": {"type": "text"},
                "description": {"type": "text"},
                "severity": {"type": "keyword"},
                "data": {"type": "object", "enabled": True},
                "correlation_id": {"type": "keyword"},
                "entity_id": {"type": "keyword"},
                "entity_type": {"type": "keyword"}
            })
        
        elif index_type == ElkIndexType.ALERTS:
            base_mapping["properties"].update({
                "alert_id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "severity": {"type": "keyword"},
                "condition": {"type": "text"},
                "triggered_at": {"type": "date"},
                "resolved_at": {"type": "date"},
                "status": {"type": "keyword"},
                "value": {"type": "float"},
                "threshold": {"type": "float"},
                "message": {"type": "text"},
                "context": {"type": "object", "enabled": True}
            })
        
        return base_mapping
    
    async def _index_rotation_loop(self) -> None:
        """Boucle de rotation des index."""
        if not self.config["rotation"]["enabled"]:
            return
        
        while self._is_running:
            await asyncio.sleep(3600)  # Toutes les heures
            
            try:
                # Création des nouveaux index si nécessaire
                for index_type in ElkIndexType:
                    index_name = self._get_index_name(index_type)
                    
                    if not await self._es.indices.exists(index=index_name):
                        mapping = self._get_index_mapping(index_type)
                        settings = self.config["index_settings"]
                        
                        await self._es.indices.create(
                            index=index_name,
                            mappings=mapping,
                            settings=settings
                        )
                        logger.info(f"Created new index: {index_name}")
                
                # Nettoyage des anciens index
                await self._cleanup_old_indices()
                
            except Exception as e:
                logger.error(f"Error in index rotation: {e}")
    
    async def _cleanup_old_indices(self) -> None:
        """Nettoie les anciens index selon les politiques de rétention."""
        try:
            pattern = f"{self.config['index_prefix']}_*"
            indices = await self._es.cat.indices(index=pattern, format="json")
            
            for index_info in indices:
                index_name = index_info.get("index", "")
                if not index_name:
                    continue
                
                # Extraction de la date
                parts = index_name.split("_")
                if len(parts) < 3:
                    continue
                
                date_part = parts[-1]
                try:
                    index_date = datetime.strptime(date_part, "%Y.%m.%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                
                # Détermination du type d'index
                index_type_str = parts[-2] if len(parts) >= 3 else "logs"
                try:
                    index_type = ElkIndexType(index_type_str)
                except ValueError:
                    continue
                
                # Rétention
                retention_days = self.config["retention"].get(index_type, ElkDataRetention.DAYS_30)
                if retention_days == ElkDataRetention.FOREVER:
                    continue
                
                # Suppression si trop vieux
                age = (datetime.now(timezone.utc) - index_date).days
                if age > retention_days.value:
                    await self._es.indices.delete(index=index_name)
                    logger.info(f"Deleted old index: {index_name} (age: {age} days)")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old indices: {e}")
    
    # ========== MÉTHODES PRIVÉES - ALERTES ==========
    
    async def _alert_check_loop(self) -> None:
        """Boucle de vérification des alertes."""
        if not self.config["alerts"]["enabled"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["alerts"]["check_interval"])
            
            try:
                # Vérification des conditions d'alerte
                await self._check_alerts()
                
            except Exception as e:
                logger.error(f"Error in alert check loop: {e}")
    
    async def _check_alerts(self) -> None:
        """Vérifie les conditions d'alerte."""
        # Exemple d'alertes prédéfinies
        alerts_config = [
            {
                "name": "high_risk_score",
                "condition": "risk_score > 0.7",
                "severity": ElkAlertSeverity.HIGH
            },
            {
                "name": "critical_risk_score",
                "condition": "risk_score > 0.9",
                "severity": ElkAlertSeverity.CRITICAL
            },
            {
                "name": "drawdown_threshold",
                "condition": "drawdown > 0.15",
                "severity": ElkAlertSeverity.HIGH
            },
            {
                "name": "sharpe_degradation",
                "condition": "sharpe < -0.5",
                "severity": ElkAlertSeverity.MEDIUM
            }
        ]
        
        for alert_config in alerts_config:
            # Vérification de la condition
            # Ici, on simule la vérification avec les données disponibles
            # Dans un système réel, on interrogerait ELK pour les métriques
            pass
    
    async def _analytics_loop(self) -> None:
        """Boucle d'analytique."""
        if not self.config["analytics"]["enabled"]:
            return
        
        while self._is_running:
            await asyncio.sleep(self.config["analytics"]["aggregation_interval"])
            
            try:
                # Agrégation des données
                await self._run_analytics()
                
            except Exception as e:
                logger.error(f"Error in analytics loop: {e}")
    
    async def _run_analytics(self) -> None:
        """Exécute les analyses."""
        try:
            # Agrégation des logs par niveau
            log_query = {
                "size": 0,
                "aggs": {
                    "levels": {
                        "terms": {"field": "level", "size": 10}
                    }
                }
            }
            log_aggs = await self.search(
                f"{self.config['index_prefix']}_logs_*",
                log_query
            )
            
            # Agrégation des métriques
            metric_query = {
                "size": 0,
                "aggs": {
                    "avg_value": {
                        "avg": {"field": "value"}
                    }
                }
            }
            metric_aggs = await self.search(
                f"{self.config['index_prefix']}_metrics_*",
                metric_query
            )
            
            # Stockage des résultats
            if self.data_manager:
                await self.data_manager.store(
                    "elk:analytics:logs",
                    log_aggs,
                    DataType.ANALYTICS
                )
                await self.data_manager.store(
                    "elk:analytics:metrics",
                    metric_aggs,
                    DataType.ANALYTICS
                )
            
        except Exception as e:
            logger.error(f"Error running analytics: {e}")
    
    # ========== MÉTHODES PRIVÉES - SYSTEM ==========
    
    async def _test_connection(self) -> bool:
        """Teste la connexion à Elasticsearch."""
        try:
            return await self._es.ping()
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(30)
            
            try:
                if await self._test_connection():
                    self._health_status = "HEALTHY"
                else:
                    self._health_status = "UNHEALTHY"
                    
                # Stockage de l'état de santé
                if self.data_manager:
                    await self.data_manager.store(
                        "elk:health",
                        self._health_status,
                        DataType.METADATA
                    )
                
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                self._health_status = "ERROR"
    
    # ========== MÉTHODES PUBLIQUES - STATS ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        return self._stats
    
    def get_health(self) -> str:
        """Récupère l'état de santé."""
        return self._health_status


# ============== CONTEXT MANAGERS ==============

class ElkLogContext:
    """Context manager pour les logs ELK."""
    
    def __init__(
        self,
        integration: ElkIntegration,
        level: ElkLogLevel = ElkLogLevel.INFO,
        module: str = "",
        **kwargs
    ):
        self.integration = integration
        self.level = level
        self.module = module
        self.kwargs = kwargs
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = datetime.now(timezone.utc)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        entry = ElkLogEntry(
            level=self.level,
            message=f"Context execution: {duration:.3f}s",
            source="ElkLogContext",
            module=self.module,
            context={
                "duration": duration,
                "success": exc_type is None,
                "error": str(exc_val) if exc_val else None
            },
            tags=["context"],
            **self.kwargs
        )
        
        await self.integration.log(entry)
        
        if exc_val:
            entry = ElkLogEntry(
                level=ElkLogLevel.ERROR,
                message=f"Error in context: {str(exc_val)}",
                source="ElkLogContext",
                module=self.module,
                traceback=''.join(traceback.format_tb(exc_tb)),
                context={"error": str(exc_val)},
                tags=["error"]
            )
            await self.integration.log(entry)


# ============== FACTORY ==============

class ElkIntegrationFactory:
    """Factory pour créer des intégrations ELK."""
    
    @staticmethod
    async def create_integration(
        hosts: List[str],
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> ElkIntegration:
        """Crée une intégration ELK."""
        integration = ElkIntegration(
            hosts=hosts,
            data_manager=data_manager,
            config=config,
            username=username,
            password=password,
            api_key=api_key
        )
        await integration.start()
        return integration


# ============== EXPORT ==============

__all__ = [
    "ElkLogLevel",
    "ElkIndexType",
    "ElkAlertSeverity",
    "ElkDataRetention",
    "ElkLogEntry",
    "ElkMetric",
    "ElkEvent",
    "ElkAlert",
    "ElkIntegration",
    "ElkLogContext",
    "ElkIntegrationFactory"
]
