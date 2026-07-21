"""
NEXUS AI TRADING SYSTEM - Hedge Bot Emergency Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire d'urgence pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import psutil
import os
import signal
import sys

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class EmergencyLevel(Enum):
    """Niveaux d'urgence"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"
    CATASTROPHIC = "catastrophic"

class EmergencyType(Enum):
    """Types d'urgence"""
    SYSTEM = "system"
    NETWORK = "network"
    EXCHANGE = "exchange"
    DATA = "data"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TRADING = "trading"
    RISK = "risk"
    RESOURCE = "resource"
    APPLICATION = "application"

class EmergencyAction(Enum):
    """Actions d'urgence"""
    LOG = "log"
    ALERT = "alert"
    PAUSE = "pause"
    STOP = "stop"
    RESTART = "restart"
    SHUTDOWN = "shutdown"
    REDUCE = "reduce"
    HEDGE = "hedge"
    LIQUIDATE = "liquidate"
    ESCALATE = "escalate"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class EmergencyEvent:
    """Événement d'urgence"""
    id: str
    level: EmergencyLevel
    type: EmergencyType
    message: str
    timestamp: float
    source: str
    details: Dict[str, Any]
    action_taken: Optional[EmergencyAction] = None
    resolved: bool = False
    resolved_at: Optional[float] = None
    resolution: Optional[str] = None

@dataclass
class EmergencyRule:
    """Règle d'urgence"""
    id: str
    name: str
    level: EmergencyLevel
    type: EmergencyType
    condition: Callable[[Dict[str, Any]], bool]
    action: EmergencyAction
    message: str
    cooldown: float = 60.0
    enabled: bool = True
    last_triggered: float = 0.0

@dataclass
class EmergencyConfig:
    """Configuration d'urgence"""
    enabled: bool = True
    auto_pause: bool = True
    auto_stop: bool = True
    max_events_per_minute: int = 10
    cooldown_period: float = 60.0
    escalation_period: float = 300.0
    alert_channels: List[str] = field(default_factory=list)
    actions: Dict[EmergencyLevel, List[EmergencyAction]] = field(default_factory=dict)

# ============================================================
# EMERGENCY MANAGER
# ============================================================

class EmergencyManager:
    """
    Gestionnaire d'urgence pour le bot de couverture
    
    Surveille, détecte et gère les situations d'urgence
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        config: Optional[EmergencyConfig] = None,
        enable_monitoring: bool = True,
        check_interval: int = 5
    ):
        """
        Initialise le gestionnaire d'urgence
        
        Args:
            config: Configuration d'urgence
            enable_monitoring: Activer le monitoring
            check_interval: Intervalle de vérification
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.config = config or EmergencyConfig()
        self.enable_monitoring = enable_monitoring
        self.check_interval = check_interval
        
        self._initialized = True
        
        # Événements
        self.events: List[EmergencyEvent] = []
        self.active_events: List[EmergencyEvent] = []
        self.event_history: List[EmergencyEvent] = []
        
        # Règles
        self.rules: List[EmergencyRule] = []
        self._load_default_rules()
        
        # État
        self._is_paused = False
        self._is_stopped = False
        self._is_shutting_down = False
        self._monitoring_task = None
        self._running = False
        
        # Statistiques
        self.stats = {
            'total_events': 0,
            'by_level': {},
            'by_type': {},
            'resolved': 0,
            'actions_taken': {},
            'last_event': None,
        }
        
        # Callbacks
        self._callbacks: Dict[EmergencyLevel, List[Callable]] = {
            level: [] for level in EmergencyLevel
        }
        
        if self.enable_monitoring:
            self.start()
        
        logger.info("EmergencyManager initialized")
    
    def _load_default_rules(self):
        """Charge les règles d'urgence par défaut"""
        # Règle 1: CPU élevé
        self.add_rule(EmergencyRule(
            id="cpu_high",
            name="High CPU Usage",
            level=EmergencyLevel.WARNING,
            type=EmergencyType.RESOURCE,
            condition=lambda d: d.get('cpu_percent', 0) > 80,
            action=EmergencyAction.ALERT,
            message="CPU usage exceeded 80%"
        ))
        
        # Règle 2: CPU critique
        self.add_rule(EmergencyRule(
            id="cpu_critical",
            name="Critical CPU Usage",
            level=EmergencyLevel.CRITICAL,
            type=EmergencyType.RESOURCE,
            condition=lambda d: d.get('cpu_percent', 0) > 95,
            action=EmergencyAction.REDUCE,
            message="CPU usage exceeded 95%"
        ))
        
        # Règle 3: Mémoire élevée
        self.add_rule(EmergencyRule(
            id="memory_high",
            name="High Memory Usage",
            level=EmergencyLevel.WARNING,
            type=EmergencyType.RESOURCE,
            condition=lambda d: d.get('memory_percent', 0) > 80,
            action=EmergencyAction.ALERT,
            message="Memory usage exceeded 80%"
        ))
        
        # Règle 4: Mémoire critique
        self.add_rule(EmergencyRule(
            id="memory_critical",
            name="Critical Memory Usage",
            level=EmergencyLevel.CRITICAL,
            type=EmergencyType.RESOURCE,
            condition=lambda d: d.get('memory_percent', 0) > 95,
            action=EmergencyAction.PAUSE,
            message="Memory usage exceeded 95%"
        ))
        
        # Règle 5: Disque plein
        self.add_rule(EmergencyRule(
            id="disk_full",
            name="Disk Full",
            level=EmergencyLevel.CRITICAL,
            type=EmergencyType.RESOURCE,
            condition=lambda d: d.get('disk_percent', 0) > 90,
            action=EmergencyAction.ALERT,
            message="Disk usage exceeded 90%"
        ))
        
        # Règle 6: Perte de connexion
        self.add_rule(EmergencyRule(
            id="connection_lost",
            name="Connection Lost",
            level=EmergencyLevel.CRITICAL,
            type=EmergencyType.NETWORK,
            condition=lambda d: not d.get('connected', True),
            action=EmergencyAction.STOP,
            message="Connection lost to exchange"
        ))
        
        # Règle 7: Erreur de trading
        self.add_rule(EmergencyRule(
            id="trading_error",
            name="Trading Error",
            level=EmergencyLevel.WARNING,
            type=EmergencyType.TRADING,
            condition=lambda d: d.get('error_rate', 0) > 0.05,
            action=EmergencyAction.PAUSE,
            message="Trading error rate exceeded 5%"
        ))
        
        # Règle 8: Drawdown élevé
        self.add_rule(EmergencyRule(
            id="drawdown_high",
            name="High Drawdown",
            level=EmergencyLevel.CRITICAL,
            type=EmergencyType.RISK,
            condition=lambda d: d.get('drawdown', 0) > 0.15,
            action=EmergencyAction.HEDGE,
            message="Drawdown exceeded 15%"
        ))
        
        # Règle 9: Drawdown critique
        self.add_rule(EmergencyRule(
            id="drawdown_critical",
            name="Critical Drawdown",
            level=EmergencyLevel.EMERGENCY,
            type=EmergencyType.RISK,
            condition=lambda d: d.get('drawdown', 0) > 0.25,
            action=EmergencyAction.LIQUIDATE,
            message="Drawdown exceeded 25%"
        ))
        
        # Règle 10: Perte de données
        self.add_rule(EmergencyRule(
            id="data_loss",
            name="Data Loss",
            level=EmergencyLevel.EMERGENCY,
            type=EmergencyType.DATA,
            condition=lambda d: d.get('data_loss', False),
            action=EmergencyAction.SHUTDOWN,
            message="Data loss detected"
        ))
    
    # ============================================================
    # RULE MANAGEMENT
    # ============================================================
    
    def add_rule(self, rule: EmergencyRule):
        """
        Ajoute une règle d'urgence
        
        Args:
            rule: Règle à ajouter
        """
        self.rules.append(rule)
        logger.info(f"Emergency rule added: {rule.name}")
    
    def remove_rule(self, rule_id: str):
        """
        Supprime une règle d'urgence
        
        Args:
            rule_id: ID de la règle
        """
        self.rules = [r for r in self.rules if r.id != rule_id]
        logger.info(f"Emergency rule removed: {rule_id}")
    
    def enable_rule(self, rule_id: str):
        """
        Active une règle d'urgence
        
        Args:
            rule_id: ID de la règle
        """
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = True
                logger.info(f"Emergency rule enabled: {rule.name}")
                break
    
    def disable_rule(self, rule_id: str):
        """
        Désactive une règle d'urgence
        
        Args:
            rule_id: ID de la règle
        """
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = False
                logger.info(f"Emergency rule disabled: {rule.name}")
                break
    
    # ============================================================
    # EVENT MANAGEMENT
    # ============================================================
    
    def trigger_event(
        self,
        level: EmergencyLevel,
        type: EmergencyType,
        message: str,
        source: str,
        details: Optional[Dict[str, Any]] = None,
        action: Optional[EmergencyAction] = None
    ) -> EmergencyEvent:
        """
        Déclenche un événement d'urgence
        
        Args:
            level: Niveau d'urgence
            type: Type d'urgence
            message: Message
            source: Source
            details: Détails
            action: Action à prendre
            
        Returns:
            EmergencyEvent: Événement créé
        """
        event = EmergencyEvent(
            id=f"emergency_{int(time.time())}_{len(self.events)}",
            level=level,
            type=type,
            message=message,
            timestamp=time.time(),
            source=source,
            details=details or {},
            action_taken=action
        )
        
        self.events.append(event)
        self.active_events.append(event)
        self.stats['total_events'] += 1
        self.stats['last_event'] = event
        
        # Mettre à jour les statistiques
        level_key = level.value
        if level_key not in self.stats['by_level']:
            self.stats['by_level'][level_key] = 0
        self.stats['by_level'][level_key] += 1
        
        type_key = type.value
        if type_key not in self.stats['by_type']:
            self.stats['by_type'][type_key] = 0
        self.stats['by_type'][type_key] += 1
        
        # Logger
        logger.log(
            self._get_log_level(level),
            f"[{level.value.upper()}] {source}: {message}",
            extra={'details': details}
        )
        
        # Exécuter l'action
        if action:
            self._execute_action(event)
        
        # Notifier les callbacks
        self._notify_callbacks(event)
        
        return event
    
    def _get_log_level(self, level: EmergencyLevel) -> int:
        """Récupère le niveau de log correspondant"""
        level_map = {
            EmergencyLevel.INFO: logging.INFO,
            EmergencyLevel.WARNING: logging.WARNING,
            EmergencyLevel.CRITICAL: logging.ERROR,
            EmergencyLevel.EMERGENCY: logging.CRITICAL,
            EmergencyLevel.CATASTROPHIC: logging.CRITICAL,
        }
        return level_map.get(level, logging.INFO)
    
    def _execute_action(self, event: EmergencyEvent):
        """
        Exécute une action d'urgence
        
        Args:
            event: Événement d'urgence
        """
        action = event.action_taken
        if not action:
            return
        
        if action in self.stats['actions_taken']:
            self.stats['actions_taken'][action.value] += 1
        else:
            self.stats['actions_taken'][action.value] = 1
        
        if action == EmergencyAction.LOG:
            logger.info(f"[ACTION] LOG: {event.message}")
        
        elif action == EmergencyAction.ALERT:
            self._send_alert(event)
        
        elif action == EmergencyAction.PAUSE:
            self._pause_operations(event)
        
        elif action == EmergencyAction.STOP:
            self._stop_operations(event)
        
        elif action == EmergencyAction.RESTART:
            self._restart_operations(event)
        
        elif action == EmergencyAction.SHUTDOWN:
            self._shutdown_system(event)
        
        elif action == EmergencyAction.REDUCE:
            self._reduce_operations(event)
        
        elif action == EmergencyAction.HEDGE:
            self._apply_hedge(event)
        
        elif action == EmergencyAction.LIQUIDATE:
            self._liquidate_positions(event)
        
        elif action == EmergencyAction.ESCALATE:
            self._escalate_issue(event)
    
    def _send_alert(self, event: EmergencyEvent):
        """Envoie une alerte"""
        logger.info(f"[ALERT] {event.level.value.upper()}: {event.message}")
        # Implémentation de l'envoi d'alerte
    
    def _pause_operations(self, event: EmergencyEvent):
        """Met en pause les opérations"""
        if self._is_paused:
            return
        
        self._is_paused = True
        logger.warning(f"[PAUSE] Operations paused: {event.message}")
        
        # Notifier l'arrêt
        self._notify_callbacks(event, 'paused')
    
    def _stop_operations(self, event: EmergencyEvent):
        """Arrête les opérations"""
        if self._is_stopped:
            return
        
        self._is_stopped = True
        logger.critical(f"[STOP] Operations stopped: {event.message}")
        
        # Notifier l'arrêt
        self._notify_callbacks(event, 'stopped')
    
    def _restart_operations(self, event: EmergencyEvent):
        """Redémarre les opérations"""
        logger.info(f"[RESTART] Restarting operations: {event.message}")
        # Implémentation du redémarrage
    
    def _shutdown_system(self, event: EmergencyEvent):
        """Arrête le système"""
        if self._is_shutting_down:
            return
        
        self._is_shutting_down = True
        logger.critical(f"[SHUTDOWN] System shutting down: {event.message}")
        
        # Notifier l'arrêt
        self._notify_callbacks(event, 'shutting_down')
        
        # Arrêter le monitoring
        self.stop()
        
        # Quitter
        sys.exit(1)
    
    def _reduce_operations(self, event: EmergencyEvent):
        """Réduit les opérations"""
        logger.info(f"[REDUCE] Reducing operations: {event.message}")
        # Implémentation de la réduction
    
    def _apply_hedge(self, event: EmergencyEvent):
        """Applique une couverture"""
        logger.info(f"[HEDGE] Applying hedge: {event.message}")
        # Implémentation de la couverture
    
    def _liquidate_positions(self, event: EmergencyEvent):
        """Liquide les positions"""
        logger.critical(f"[LIQUIDATE] Liquidating positions: {event.message}")
        # Implémentation de la liquidation
    
    def _escalate_issue(self, event: EmergencyEvent):
        """Escalade le problème"""
        logger.critical(f"[ESCALATE] Escalating issue: {event.message}")
        # Implémentation de l'escalade
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def add_callback(
        self,
        level: EmergencyLevel,
        callback: Callable[[EmergencyEvent], None]
    ):
        """
        Ajoute un callback pour un niveau d'urgence
        
        Args:
            level: Niveau d'urgence
            callback: Fonction de callback
        """
        self._callbacks[level].append(callback)
    
    def remove_callback(
        self,
        level: EmergencyLevel,
        callback: Callable[[EmergencyEvent], None]
    ):
        """
        Supprime un callback
        
        Args:
            level: Niveau d'urgence
            callback: Fonction de callback
        """
        if callback in self._callbacks[level]:
            self._callbacks[level].remove(callback)
    
    def _notify_callbacks(self, event: EmergencyEvent, status: str = "triggered"):
        """
        Notifie les callbacks
        
        Args:
            event: Événement d'urgence
            status: Statut de l'événement
        """
        for callback in self._callbacks.get(event.level, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ============================================================
    # RESOLUTION
    # ============================================================
    
    def resolve_event(self, event_id: str, resolution: str):
        """
        Résout un événement d'urgence
        
        Args:
            event_id: ID de l'événement
            resolution: Résolution
        """
        for event in self.active_events:
            if event.id == event_id:
                event.resolved = True
                event.resolved_at = time.time()
                event.resolution = resolution
                self.active_events.remove(event)
                self.event_history.append(event)
                self.stats['resolved'] += 1
                logger.info(f"Emergency resolved: {event_id} - {resolution}")
                break
    
    def resolve_all(self, resolution: str = "Manual resolution"):
        """
        Résout tous les événements actifs
        
        Args:
            resolution: Résolution
        """
        for event in self.active_events[:]:
            self.resolve_event(event.id, resolution)
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._monitoring_task = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitoring_task.start()
        
        logger.info("Emergency monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.join(timeout=2)
        
        logger.info("Emergency monitoring stopped")
    
    def _monitor_loop(self):
        """Boucle de monitoring"""
        while self._running:
            try:
                # Collecter les métriques
                metrics = self._collect_metrics()
                
                # Vérifier les règles
                self._check_rules(metrics)
                
                # Nettoyer les événements anciens
                self._cleanup_events()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(self.check_interval)
    
    def _collect_metrics(self) -> Dict[str, Any]:
        """
        Collecte les métriques système
        
        Returns:
            Dict[str, Any]: Métriques
        """
        metrics = {
            'timestamp': time.time(),
            'cpu_percent': psutil.cpu_percent(interval=0.5),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'connected': True,  # À remplacer par la vérification réelle
            'error_rate': 0.0,  # À remplacer par le taux d'erreur réel
            'drawdown': 0.0,    # À remplacer par le drawdown réel
            'data_loss': False,
        }
        
        return metrics
    
    def _check_rules(self, metrics: Dict[str, Any]):
        """
        Vérifie les règles d'urgence
        
        Args:
            metrics: Métriques collectées
        """
        now = time.time()
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Vérifier le cooldown
            if now - rule.last_triggered < rule.cooldown:
                continue
            
            # Vérifier la condition
            try:
                if rule.condition(metrics):
                    rule.last_triggered = now
                    self.trigger_event(
                        level=rule.level,
                        type=rule.type,
                        message=rule.message,
                        source=rule.name,
                        details=metrics,
                        action=rule.action
                    )
            except Exception as e:
                logger.error(f"Rule check error for {rule.name}: {e}")
    
    def _cleanup_events(self):
        """Nettoie les événements anciens"""
        now = time.time()
        cutoff = now - 3600  # 1 heure
        
        # Nettoyer l'historique
        self.event_history = [
            e for e in self.event_history
            if e.timestamp > cutoff
        ]
        
        # Limiter le nombre d'événements
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
    
    # ============================================================
    # STATUS AND STATISTICS
    # ============================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Récupère le statut du gestionnaire
        
        Returns:
            Dict[str, Any]: Statut
        """
        return {
            'initialized': self._initialized,
            'running': self._running,
            'paused': self._is_paused,
            'stopped': self._is_stopped,
            'shutting_down': self._is_shutting_down,
            'active_events': len(self.active_events),
            'total_events': self.stats['total_events'],
            'resolved_events': self.stats['resolved'],
            'rules_count': len(self.rules),
            'enabled_rules': sum(1 for r in self.rules if r.enabled),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            **self.stats,
            'active_events': [
                {
                    'id': e.id,
                    'level': e.level.value,
                    'type': e.type.value,
                    'message': e.message,
                    'timestamp': e.timestamp,
                    'source': e.source,
                }
                for e in self.active_events
            ],
            'recent_events': [
                {
                    'id': e.id,
                    'level': e.level.value,
                    'type': e.type.value,
                    'message': e.message,
                    'timestamp': e.timestamp,
                    'source': e.source,
                }
                for e in self.events[-10:]
            ],
        }
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """
        Récupère les règles d'urgence
        
        Returns:
            List[Dict[str, Any]]: Règles
        """
        return [
            {
                'id': r.id,
                'name': r.name,
                'level': r.level.value,
                'type': r.type.value,
                'action': r.action.value,
                'message': r.message,
                'enabled': r.enabled,
                'last_triggered': r.last_triggered,
            }
            for r in self.rules
        ]
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def is_paused(self) -> bool:
        """Vérifie si les opérations sont en pause"""
        return self._is_paused
    
    def is_stopped(self) -> bool:
        """Vérifie si les opérations sont arrêtées"""
        return self._is_stopped
    
    def resume(self):
        """Reprend les opérations"""
        if not self._is_paused:
            return
        
        self._is_paused = False
        logger.info("Operations resumed")
    
    def restart(self):
        """Redémarre les opérations"""
        self._is_stopped = False
        self._is_paused = False
        logger.info("Operations restarted")

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_emergency_manager: Optional[EmergencyManager] = None

def get_emergency_manager(
    config: Optional[EmergencyConfig] = None,
    enable_monitoring: bool = True
) -> EmergencyManager:
    """
    Récupère le gestionnaire d'urgence (singleton)
    
    Args:
        config: Configuration d'urgence
        enable_monitoring: Activer le monitoring
        
    Returns:
        EmergencyManager: Gestionnaire d'urgence
    """
    global _emergency_manager
    if _emergency_manager is None:
        _emergency_manager = EmergencyManager(
            config=config,
            enable_monitoring=enable_monitoring
        )
    return _emergency_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'EmergencyLevel',
    'EmergencyType',
    'EmergencyAction',
    'EmergencyEvent',
    'EmergencyRule',
    'EmergencyConfig',
    'EmergencyManager',
    'get_emergency_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Emergency manager module initialized")
