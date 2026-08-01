# trading/bots/hedge_bot/hedge_bot_data_notified.py
# Advanced Data Notification & Event-Driven Alert Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Notified Module - Module avancé de notifications de données et d'alertes événementielles
pour le Hedge Bot. Gère les notifications basées sur les données, les alertes événementielles,
les triggers de données, les règles de notification et les escalades pour le système de hedging.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import hashlib
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_notified")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_notification import (
    NotificationEngine, Notification, NotificationType, NotificationPriority,
    NotificationChannel, NotificationBuilder
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class DataTriggerType(Enum):
    """Types de triggers de données."""
    THRESHOLD = "threshold"            # Dépassement de seuil
    CHANGE = "change"                  # Changement de valeur
    RATE = "rate"                      # Taux de changement
    ANOMALY = "anomaly"                # Détection d'anomalie
    PATTERN = "pattern"                # Détection de pattern
    COMPARISON = "comparison"          # Comparaison entre valeurs
    TIMER = "timer"                    # Déclencheur temporel
    COMPOUND = "compound"              # Condition composée


class DataTriggerOperator(Enum):
    """Opérateurs de comparaison."""
    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"


class EscalationPolicy(Enum):
    """Politiques d'escalade."""
    NONE = "none"                      # Pas d'escalade
    TIME_BASED = "time_based"          # Basée sur le temps
    ATTEMPT_BASED = "attempt_based"    # Basée sur les tentatives
    SEVERITY_BASED = "severity_based"  # Basée sur la sévérité


# ============== DATA MODELS ==============

@dataclass
class DataTrigger:
    """Trigger de données."""
    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    data_type: DataType = DataType.MARKET
    trigger_type: DataTriggerType = DataTriggerType.THRESHOLD
    source: str = ""
    field: str = ""
    operator: DataTriggerOperator = DataTriggerOperator.GT
    value: Any = None
    value2: Optional[Any] = None
    window: int = 0  # Window en secondes pour les taux
    frequency: int = 0  # Fréquence d'évaluation en secondes
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_triggered: Optional[datetime] = None
    cooldown: int = 60  # Cooldown en secondes


@dataclass
class DataNotificationRule:
    """Règle de notification de données."""
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    trigger_id: str = ""
    notification_template: str = ""
    channels: List[NotificationChannel] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    priority: NotificationPriority = NotificationPriority.MEDIUM
    escalation_policy: EscalationPolicy = EscalationPolicy.NONE
    escalation_levels: List[Dict[str, Any]] = field(default_factory=list)
    dedup_window: int = 300
    cooldown: int = 300
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataNotificationEvent:
    """Événement de notification de données."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    trigger_id: str = ""
    data: Any = None
    trigger_value: float = 0.0
    threshold_value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed: bool = False
    sent: bool = False
    escalation_level: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class DataNotifiedEngineInterface(ABC):
    """Interface abstraite pour le moteur de notifications de données."""
    
    @abstractmethod
    async def create_trigger(self, trigger: DataTrigger) -> str:
        """Crée un trigger de données."""
        pass
    
    @abstractmethod
    async def create_rule(self, rule: DataNotificationRule) -> str:
        """Crée une règle de notification."""
        pass
    
    @abstractmethod
    async def process_data(self, data: Any, data_type: DataType) -> List[DataNotificationEvent]:
        """Traite des données pour déclencher des notifications."""
        pass
    
    @abstractmethod
    async def get_events(self, rule_id: str) -> List[DataNotificationEvent]:
        """Récupère les événements d'une règle."""
        pass


# ============== IMPLÉMENTATION ==============

class DataNotifiedEngine(DataNotifiedEngineInterface):
    """
    Moteur de notifications de données avancé pour le Hedge Bot.
    Gère les notifications basées sur les données et les alertes événementielles.
    """
    
    def __init__(
        self,
        notification_engine: NotificationEngine,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.notification_engine = notification_engine
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des triggers
        self._triggers: Dict[str, DataTrigger] = {}
        self._triggers_lock = threading.RLock()
        
        # Gestion des règles
        self._rules: Dict[str, DataNotificationRule] = {}
        self._rules_lock = threading.RLock()
        
        # Gestion des événements
        self._events: Dict[str, DataNotificationEvent] = {}
        self._events_lock = threading.RLock()
        
        # Cache d'évaluation
        self._eval_cache: Dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        
        # Queue d'événements
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "triggers_created": 0,
            "rules_created": 0,
            "events_generated": 0,
            "notifications_sent": 0,
            "escalations_performed": 0,
            "avg_eval_time_ms": 0.0,
            "events_pending": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("DataNotifiedEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_cooldown": 60,
            "eval_interval": 10,
            "max_cache_size": 10000,
            "enable_dedup": True,
            "dedup_window": 300,
            "max_events_per_second": 100,
            "escalation_interval": 60,
            "event_retention_days": 30,
            "default_priority": NotificationPriority.MEDIUM,
            "default_channels": [NotificationChannel.EMAIL, NotificationChannel.SLACK],
            "enable_debug_logging": False
        }
    
    async def start(self) -> None:
        """Démarre le moteur de notifications de données."""
        logger.info("DataNotifiedEngine starting...")
        self._is_running = True
        
        # Chargement des triggers
        await self._load_triggers()
        
        # Chargement des règles
        await self._load_rules()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._event_processor())
        asyncio.create_task(self._trigger_evaluator())
        asyncio.create_task(self._escalation_monitor())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("DataNotifiedEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de notifications de données."""
        logger.info("DataNotifiedEngine stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("DataNotifiedEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_trigger(self, trigger: DataTrigger) -> str:
        """Crée un trigger de données."""
        with self._triggers_lock:
            self._triggers[trigger.trigger_id] = trigger
            self._stats["triggers_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"notified:trigger:{trigger.trigger_id}",
                trigger.to_dict(),
                DataType.TRIGGER
            )
        
        logger.info(f"Data trigger created: {trigger.name} (id={trigger.trigger_id})")
        return trigger.trigger_id
    
    async def create_rule(self, rule: DataNotificationRule) -> str:
        """Crée une règle de notification."""
        with self._rules_lock:
            self._rules[rule.rule_id] = rule
            self._stats["rules_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"notified:rule:{rule.rule_id}",
                rule.to_dict(),
                DataType.RULE
            )
        
        logger.info(f"Data notification rule created: {rule.name} (id={rule.rule_id})")
        return rule.rule_id
    
    async def process_data(self, data: Any, data_type: DataType) -> List[DataNotificationEvent]:
        """Traite des données pour déclencher des notifications."""
        events = []
        
        # Récupération des triggers actifs
        with self._triggers_lock:
            triggers = [t for t in self._triggers.values() if t.active]
        
        for trigger in triggers:
            if trigger.data_type != data_type:
                continue
            
            # Évaluation du trigger
            if await self._evaluate_trigger(trigger, data):
                # Création de l'événement
                event = DataNotificationEvent(
                    rule_id="",  # Sera rempli par les règles
                    trigger_id=trigger.trigger_id,
                    data=data,
                    trigger_value=self._extract_value(data, trigger.field),
                    threshold_value=trigger.value
                )
                events.append(event)
        
        # Traitement des événements
        for event in events:
            await self._handle_event(event)
        
        return events
    
    async def get_events(self, rule_id: str) -> List[DataNotificationEvent]:
        """Récupère les événements d'une règle."""
        with self._events_lock:
            return [e for e in self._events.values() if e.rule_id == rule_id]
    
    # ========== MÉTHODES PRIVÉES - TRIGGERS ==========
    
    async def _evaluate_trigger(self, trigger: DataTrigger, data: Any) -> bool:
        """Évalue un trigger."""
        try:
            # Extraction de la valeur
            value = self._extract_value(data, trigger.field)
            
            # Évaluation selon le type
            if trigger.trigger_type == DataTriggerType.THRESHOLD:
                return self._evaluate_threshold(value, trigger.operator, trigger.value)
            
            elif trigger.trigger_type == DataTriggerType.CHANGE:
                # Vérification du changement
                previous = await self._get_previous_value(trigger, data)
                if previous is not None:
                    change = abs(value - previous)
                    return self._evaluate_threshold(change, trigger.operator, trigger.value)
                return False
            
            elif trigger.trigger_type == DataTriggerType.RATE:
                # Vérification du taux de changement
                previous = await self._get_previous_value(trigger, data)
                if previous is not None and trigger.window > 0:
                    rate = abs(value - previous) / trigger.window
                    return self._evaluate_threshold(rate, trigger.operator, trigger.value)
                return False
            
            elif trigger.trigger_type == DataTriggerType.COMPOUND:
                # Évaluation des conditions composées
                return await self._evaluate_compound(trigger, data)
            
            elif trigger.trigger_type == DataTriggerType.PATTERN:
                # Évaluation de pattern (simplifiée)
                return self._evaluate_pattern(trigger, data)
            
            else:
                return False
                
        except Exception as e:
            logger.error(f"Trigger evaluation error: {e}")
            return False
    
    def _extract_value(self, data: Any, field: str) -> float:
        """Extrait une valeur d'une donnée."""
        if isinstance(data, dict):
            return data.get(field, 0.0)
        elif isinstance(data, (int, float)):
            return float(data)
        else:
            return 0.0
    
    def _evaluate_threshold(self, value: float, operator: DataTriggerOperator, threshold: float) -> bool:
        """Évalue un seuil."""
        if operator == DataTriggerOperator.GT:
            return value > threshold
        elif operator == DataTriggerOperator.GTE:
            return value >= threshold
        elif operator == DataTriggerOperator.LT:
            return value < threshold
        elif operator == DataTriggerOperator.LTE:
            return value <= threshold
        elif operator == DataTriggerOperator.EQ:
            return value == threshold
        elif operator == DataTriggerOperator.NE:
            return value != threshold
        elif operator == DataTriggerOperator.BETWEEN:
            return threshold[0] <= value <= threshold[1]
        else:
            return False
    
    async def _get_previous_value(self, trigger: DataTrigger, data: Any) -> Optional[float]:
        """Récupère la valeur précédente."""
        # Dans un système réel, on interrogerait l'historique
        cache_key = f"{trigger.trigger_id}_{trigger.field}"
        with self._cache_lock:
            return self._eval_cache.get(cache_key)
    
    async def _evaluate_compound(self, trigger: DataTrigger, data: Any) -> bool:
        """Évalue une condition composée."""
        if not trigger.conditions:
            return False
        
        results = []
        for condition in trigger.conditions:
            field = condition.get("field", "")
            operator = DataTriggerOperator(condition.get("operator", ">"))
            value = condition.get("value", 0)
            
            field_value = self._extract_value(data, field)
            result = self._evaluate_threshold(field_value, operator, value)
            results.append(result)
        
        # Toutes les conditions doivent être vraies
        return all(results)
    
    def _evaluate_pattern(self, trigger: DataTrigger, data: Any) -> bool:
        """Évalue un pattern."""
        # Simplification - pattern matching basique
        pattern = trigger.value
        if isinstance(pattern, str) and isinstance(data, dict):
            import re
            for key, value in data.items():
                if re.search(pattern, str(value)):
                    return True
        return False
    
    # ========== MÉTHODES PRIVÉES - ÉVÉNEMENTS ==========
    
    async def _handle_event(self, event: DataNotificationEvent) -> None:
        """Gère un événement."""
        # Recherche des règles associées
        with self._rules_lock:
            rules = [r for r in self._rules.values() if r.trigger_id == event.trigger_id and r.active]
        
        for rule in rules:
            # Vérification du cooldown
            if rule.cooldown > 0:
                last_events = await self.get_events(rule.rule_id)
                if last_events:
                    last = max(e.timestamp for e in last_events)
                    if (datetime.now(timezone.utc) - last).total_seconds() < rule.cooldown:
                        continue
            
            event.rule_id = rule.rule_id
            event.processed = True
            
            with self._events_lock:
                self._events[event.event_id] = event
                self._stats["events_generated"] += 1
            
            # Mise en queue
            await self._event_queue.put((rule, event))
    
    async def _event_processor(self) -> None:
        """Traite les événements en queue."""
        while self._is_running:
            try:
                rule, event = await self._event_queue.get()
                
                # Envoi de la notification
                await self._send_notification(rule, event)
                
                # Gestion de l'escalade
                if rule.escalation_policy != EscalationPolicy.NONE:
                    asyncio.create_task(self._handle_escalation(rule, event))
                
            except Exception as e:
                logger.error(f"Event processor error: {e}")
                await asyncio.sleep(1)
    
    async def _send_notification(self, rule: DataNotificationRule, event: DataNotificationEvent) -> None:
        """Envoie une notification."""
        try:
            # Construction de la notification
            builder = NotificationBuilder()
            
            notification = (
                builder
                .type(NotificationType.ALERT)
                .priority(rule.priority)
                .title(f"Data Alert: {rule.name}")
                .message(f"Triggered by {event.trigger_id}\nValue: {event.trigger_value}\nThreshold: {event.threshold_value}")
                .channels(rule.channels)
                .recipients(rule.recipients)
                .data({"event": event.to_dict()})
                .tags(["data_alert", rule.name])
                .build()
            )
            
            # Envoi de la notification
            sent = await self.notification_engine.send(notification)
            
            if sent:
                event.sent = True
                self._stats["notifications_sent"] += 1
                logger.info(f"Notification sent for rule: {rule.name}")
            else:
                logger.warning(f"Notification failed for rule: {rule.name}")
                
        except Exception as e:
            logger.error(f"Notification send error: {e}")
    
    # ========== MÉTHODES PRIVÉES - ESCALADE ==========
    
    async def _escalation_monitor(self) -> None:
        """Monitor les escalades."""
        while self._is_running:
            await asyncio.sleep(self.config["escalation_interval"])
            
            try:
                with self._events_lock:
                    for event in self._events.values():
                        if not event.processed or event.sent:
                            continue
                        
                        # Vérification des escalades en attente
                        with self._rules_lock:
                            rule = self._rules.get(event.rule_id)
                            if not rule or rule.escalation_policy == EscalationPolicy.NONE:
                                continue
                            
                            # Exécution de l'escalade
                            await self._handle_escalation(rule, event)
                
            except Exception as e:
                logger.error(f"Escalation monitor error: {e}")
    
    async def _handle_escalation(self, rule: DataNotificationRule, event: DataNotificationEvent) -> None:
        """Gère l'escalade d'un événement."""
        if not rule.escalation_levels:
            return
        
        # Détermination du niveau d'escalade
        current_level = event.escalation_level
        if current_level >= len(rule.escalation_levels):
            return
        
        level_config = rule.escalation_levels[current_level]
        
        # Critères d'escalade
        if rule.escalation_policy == EscalationPolicy.TIME_BASED:
            # Basée sur le temps
            elapsed = (datetime.now(timezone.utc) - event.timestamp).total_seconds()
            if elapsed < level_config.get("timeout", 300):
                return
        
        elif rule.escalation_policy == EscalationPolicy.ATTEMPT_BASED:
            # Basée sur les tentatives
            if event.escalation_level < level_config.get("attempts", 1):
                return
        
        # Exécution de l'escalade
        event.escalation_level = current_level + 1
        self._stats["escalations_performed"] += 1
        
        # Envoi de la notification d'escalade
        await self._send_escalation_notification(rule, event, level_config)
    
    async def _send_escalation_notification(
        self,
        rule: DataNotificationRule,
        event: DataNotificationEvent,
        level_config: Dict[str, Any]
    ) -> None:
        """Envoie une notification d'escalade."""
        try:
            builder = NotificationBuilder()
            
            notification = (
                builder
                .type(NotificationType.CRITICAL)
                .priority(NotificationPriority.CRITICAL)
                .title(f"ESCALATION: {rule.name}")
                .message(f"Escalation Level {event.escalation_level}\n{level_config.get('message', '')}")
                .channels(level_config.get("channels", rule.channels))
                .recipients(level_config.get("recipients", rule.recipients))
                .data({"event": event.to_dict(), "escalation_level": event.escalation_level})
                .tags(["escalation", rule.name])
                .build()
            )
            
            await self.notification_engine.send(notification)
            
        except Exception as e:
            logger.error(f"Escalation notification error: {e}")
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _trigger_evaluator(self) -> None:
        """Évalue périodiquement les triggers."""
        while self._is_running:
            await asyncio.sleep(self.config["eval_interval"])
            
            try:
                # Récupération des données récentes
                if self.data_manager:
                    for data_type in DataType:
                        data = await self.data_manager.retrieve(data_type)
                        if data:
                            await self.process_data(data, data_type)
                
            except Exception as e:
                logger.error(f"Trigger evaluator error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._eval_cache) > self.config["max_cache_size"]:
                        keys = list(self._eval_cache.keys())
                        for key in keys[:len(self._eval_cache) - self.config["max_cache_size"]]:
                            del self._eval_cache[key]
                
                # Nettoyage des événements anciens
                with self._events_lock:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["event_retention_days"])
                    old_events = [
                        eid for eid, event in self._events.items()
                        if event.timestamp < cutoff
                    ]
                    for eid in old_events:
                        del self._events[eid]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._triggers_lock:
                    self._stats["total_triggers"] = len(self._triggers)
                    active_triggers = len([t for t in self._triggers.values() if t.active])
                    self._stats["active_triggers"] = active_triggers
                
                with self._rules_lock:
                    self._stats["total_rules"] = len(self._rules)
                    active_rules = len([r for r in self._rules.values() if r.active])
                    self._stats["active_rules"] = active_rules
                
                with self._events_lock:
                    self._stats["total_events"] = len(self._events)
                    pending_events = len([e for e in self._events.values() if not e.processed])
                    self._stats["events_pending"] = pending_events
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "notified:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'événements."""
        while not self._event_queue.empty():
            try:
                rule, event = await self._event_queue.get()
                event.processed = False
            except Exception:
                break
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_triggers(self) -> None:
        """Charge les triggers existants."""
        try:
            if self.data_manager:
                triggers_data = await self.data_manager.retrieve(
                    "notified:triggers",
                    DataType.TRIGGER
                )
                
                if triggers_data:
                    for trigger_dict in triggers_data:
                        trigger = self._deserialize_trigger(trigger_dict)
                        if trigger:
                            with self._triggers_lock:
                                self._triggers[trigger.trigger_id] = trigger
            
            logger.info(f"Loaded {len(self._triggers)} data triggers")
            
        except Exception as e:
            logger.error(f"Load triggers error: {e}")
    
    async def _load_rules(self) -> None:
        """Charge les règles existantes."""
        try:
            if self.data_manager:
                rules_data = await self.data_manager.retrieve(
                    "notified:rules",
                    DataType.RULE
                )
                
                if rules_data:
                    for rule_dict in rules_data:
                        rule = self._deserialize_rule(rule_dict)
                        if rule:
                            with self._rules_lock:
                                self._rules[rule.rule_id] = rule
            
            logger.info(f"Loaded {len(self._rules)} notification rules")
            
        except Exception as e:
            logger.error(f"Load rules error: {e}")
    
    def _deserialize_trigger(self, data: Dict) -> Optional[DataTrigger]:
        """Désérialise un trigger."""
        try:
            return DataTrigger(
                trigger_id=data.get("trigger_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                data_type=DataType(data.get("data_type", "market")),
                trigger_type=DataTriggerType(data.get("trigger_type", "threshold")),
                source=data.get("source", ""),
                field=data.get("field", ""),
                operator=DataTriggerOperator(data.get("operator", ">")),
                value=data.get("value"),
                value2=data.get("value2"),
                window=data.get("window", 0),
                frequency=data.get("frequency", 0),
                conditions=data.get("conditions", []),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                last_triggered=datetime.fromisoformat(data.get("last_triggered")) if data.get("last_triggered") else None,
                cooldown=data.get("cooldown", 60)
            )
        except Exception as e:
            logger.error(f"Error deserializing trigger: {e}")
            return None
    
    def _deserialize_rule(self, data: Dict) -> Optional[DataNotificationRule]:
        """Désérialise une règle."""
        try:
            return DataNotificationRule(
                rule_id=data.get("rule_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                trigger_id=data.get("trigger_id", ""),
                notification_template=data.get("notification_template", ""),
                channels=[NotificationChannel(c) for c in data.get("channels", [])],
                recipients=data.get("recipients", []),
                priority=NotificationPriority(data.get("priority", "medium")),
                escalation_policy=EscalationPolicy(data.get("escalation_policy", "none")),
                escalation_levels=data.get("escalation_levels", []),
                dedup_window=data.get("dedup_window", 300),
                cooldown=data.get("cooldown", 300),
                active=data.get("active", True),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing rule: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_trigger(self, trigger_id: str) -> Optional[DataTrigger]:
        """Récupère un trigger."""
        with self._triggers_lock:
            return self._triggers.get(trigger_id)
    
    async def get_triggers(self) -> List[DataTrigger]:
        """Récupère les triggers."""
        with self._triggers_lock:
            return list(self._triggers.values())
    
    async def get_rule(self, rule_id: str) -> Optional[DataNotificationRule]:
        """Récupère une règle."""
        with self._rules_lock:
            return self._rules.get(rule_id)
    
    async def get_rules(self, trigger_id: Optional[str] = None) -> List[DataNotificationRule]:
        """Récupère les règles."""
        with self._rules_lock:
            rules = list(self._rules.values())
            if trigger_id:
                rules = [r for r in rules if r.trigger_id == trigger_id]
            return rules
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._triggers_lock:
            self._stats["total_triggers"] = len(self._triggers)
        with self._rules_lock:
            self._stats["total_rules"] = len(self._rules)
        with self._events_lock:
            self._stats["total_events"] = len(self._events)
        
        return self._stats.copy()


# ============== DATA NOTIFIED BUILDER ==============

class DataNotifiedBuilder:
    """
    Constructeur de notifications de données.
    Facilite la création de triggers et de règles.
    """
    
    def __init__(self):
        self._trigger = DataTrigger()
        self._rule = DataNotificationRule()
    
    def trigger_name(self, name: str) -> 'DataNotifiedBuilder':
        """Définit le nom du trigger."""
        self._trigger.name = name
        return self
    
    def trigger_type(self, trigger_type: DataTriggerType) -> 'DataNotifiedBuilder':
        """Définit le type de trigger."""
        self._trigger.trigger_type = trigger_type
        return self
    
    def field(self, field: str) -> 'DataNotifiedBuilder':
        """Définit le champ à surveiller."""
        self._trigger.field = field
        return self
    
    def threshold(self, operator: DataTriggerOperator, value: Any) -> 'DataNotifiedBuilder':
        """Définit le seuil."""
        self._trigger.operator = operator
        self._trigger.value = value
        return self
    
    def rule_name(self, name: str) -> 'DataNotifiedBuilder':
        """Définit le nom de la règle."""
        self._rule.name = name
        return self
    
    def channels(self, channels: List[NotificationChannel]) -> 'DataNotifiedBuilder':
        """Définit les canaux."""
        self._rule.channels = channels
        return self
    
    def recipients(self, recipients: List[str]) -> 'DataNotifiedBuilder':
        """Définit les destinataires."""
        self._rule.recipients = recipients
        return self
    
    def priority(self, priority: NotificationPriority) -> 'DataNotifiedBuilder':
        """Définit la priorité."""
        self._rule.priority = priority
        return self
    
    def escalation(self, policy: EscalationPolicy, levels: List[Dict[str, Any]]) -> 'DataNotifiedBuilder':
        """Définit l'escalade."""
        self._rule.escalation_policy = policy
        self._rule.escalation_levels = levels
        return self
    
    def build_trigger(self) -> DataTrigger:
        """Construit le trigger."""
        return self._trigger
    
    def build_rule(self, trigger_id: str) -> DataNotificationRule:
        """Construit la règle."""
        self._rule.trigger_id = trigger_id
        return self._rule


# ============== FACTORY ==============

class DataNotifiedFactory:
    """Factory pour créer des composants de notifications de données."""
    
    @staticmethod
    async def create_engine(
        notification_engine: NotificationEngine,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> DataNotifiedEngine:
        """Crée un moteur de notifications de données."""
        engine = DataNotifiedEngine(
            notification_engine=notification_engine,
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_builder() -> DataNotifiedBuilder:
        """Crée un constructeur."""
        return DataNotifiedBuilder()


# ============== EXPORT ==============

__all__ = [
    "DataTriggerType",
    "DataTriggerOperator",
    "EscalationPolicy",
    "DataTrigger",
    "DataNotificationRule",
    "DataNotificationEvent",
    "DataNotifiedEngineInterface",
    "DataNotifiedEngine",
    "DataNotifiedBuilder",
    "DataNotifiedFactory"
]
