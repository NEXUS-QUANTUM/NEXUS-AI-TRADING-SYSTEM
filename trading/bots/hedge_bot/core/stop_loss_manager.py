"""
NEXUS AI TRADING SYSTEM - Hedge Bot Stop Loss Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de stop loss pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import math
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import numpy as np

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class StopLossType(Enum):
    """Types de stop loss"""
    FIXED = "fixed"
    TRAILING = "trailing"
    DYNAMIC = "dynamic"
    VOLATILITY = "volatility"
    TIME_BASED = "time_based"
    PARABOLIC = "parabolic"
    ATR = "atr"
    CUSTOM = "custom"

class StopLossStatus(Enum):
    """Statuts de stop loss"""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAUSED = "paused"

class StopLossAction(Enum):
    """Actions de stop loss"""
    MARKET = "market"
    LIMIT = "limit"
    TRAILING = "trailing"
    PARTIAL = "partial"
    FULL = "full"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class StopLossLevel:
    """Niveau de stop loss"""
    id: str
    price: float
    size: float
    type: StopLossType
    action: StopLossAction
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StopLossOrder:
    """Ordre de stop loss"""
    id: str
    symbol: str
    position_id: str
    side: str
    quantity: float
    stop_price: float
    limit_price: Optional[float]
    current_price: float
    highest_price: float
    lowest_price: float
    type: StopLossType
    status: StopLossStatus
    created_at: datetime
    triggered_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StopLossConfig:
    """Configuration de stop loss"""
    enabled: bool = True
    default_type: StopLossType = StopLossType.TRAILING
    default_percentage: float = 0.02
    default_offset: float = 0.01
    min_percentage: float = 0.005
    max_percentage: float = 0.10
    default_action: StopLossAction = StopLossAction.MARKET
    partial_size: float = 0.5
    atr_period: int = 14
    atr_multiplier: float = 2.0
    volatility_period: int = 20
    volatility_multiplier: float = 2.0
    time_based_duration: int = 3600  # seconds
    trailing_activation: float = 0.01
    trailing_offset: float = 0.01
    max_drawdown: float = 0.15
    max_loss_per_day: float = 0.05
    consecutive_loss_limit: int = 3

# ============================================================
# STOP LOSS MANAGER
# ============================================================

class StopLossManager:
    """
    Gestionnaire de stop loss pour le bot de couverture
    
    Gère les stop loss pour les positions de couverture
    """
    
    def __init__(
        self,
        config: Optional[StopLossConfig] = None,
        update_interval: int = 1,
        enable_monitoring: bool = True
    ):
        """
        Initialise le gestionnaire de stop loss
        
        Args:
            config: Configuration de stop loss
            update_interval: Intervalle de mise à jour
            enable_monitoring: Activer le monitoring
        """
        self.config = config or StopLossConfig()
        self.update_interval = update_interval
        self.enable_monitoring = enable_monitoring
        
        # Ordres de stop loss
        self.orders: Dict[str, StopLossOrder] = {}
        self.active_orders: Dict[str, StopLossOrder] = {}
        self.triggered_orders: Dict[str, StopLossOrder] = {}
        self.cancelled_orders: Dict[str, StopLossOrder] = {}
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Statistiques
        self.stats = {
            'total_orders': 0,
            'active_orders': 0,
            'triggered_orders': 0,
            'cancelled_orders': 0,
            'by_type': {},
            'by_action': {},
            'total_saved': 0.0,
            'total_triggered': 0.0,
            'success_rate': 0.0,
            'avg_trigger_price': 0.0,
            'avg_saved_amount': 0.0,
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._update_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'triggered': [],
            'cancelled': [],
            'updated': [],
        }
        
        # Démarrer le monitoring
        if enable_monitoring and update_interval > 0:
            self.start()
        
        logger.info("StopLossManager initialized")
    
    # ============================================================
    # ORDER MANAGEMENT
    # ============================================================
    
    def create_order(
        self,
        symbol: str,
        position_id: str,
        side: str,
        quantity: float,
        current_price: float,
        stop_type: Optional[StopLossType] = None,
        stop_percentage: Optional[float] = None,
        stop_offset: Optional[float] = None,
        limit_price: Optional[float] = None,
        action: Optional[StopLossAction] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StopLossOrder:
        """
        Crée un ordre de stop loss
        
        Args:
            symbol: Symbole
            position_id: ID de la position
            side: Côté (BUY/SELL)
            quantity: Quantité
            current_price: Prix actuel
            stop_type: Type de stop loss
            stop_percentage: Pourcentage de stop
            stop_offset: Offset de trailing
            limit_price: Prix limit
            action: Action
            metadata: Métadonnées
            
        Returns:
            StopLossOrder: Ordre créé
        """
        with self._lock:
            stop_type = stop_type or self.config.default_type
            action = action or self.config.default_action
            
            # Calculer le prix de stop
            stop_price = self._calculate_stop_price(
                current_price=current_price,
                side=side,
                stop_type=stop_type,
                stop_percentage=stop_percentage or self.config.default_percentage,
                stop_offset=stop_offset or self.config.default_offset
            )
            
            order = StopLossOrder(
                id=f"sl_{int(time.time())}_{symbol}",
                symbol=symbol,
                position_id=position_id,
                side=side,
                quantity=quantity,
                stop_price=stop_price,
                limit_price=limit_price,
                current_price=current_price,
                highest_price=current_price,
                lowest_price=current_price,
                type=stop_type,
                status=StopLossStatus.ACTIVE,
                created_at=datetime.now(),
                triggered_at=None,
                metadata=metadata or {}
            )
            
            self.orders[order.id] = order
            self.active_orders[order.id] = order
            self.stats['total_orders'] += 1
            self.stats['active_orders'] = len(self.active_orders)
            
            self._update_stats()
            
            logger.info(f"Stop loss order created: {order.id} @ {stop_price:.2f}")
            return order
    
    def _calculate_stop_price(
        self,
        current_price: float,
        side: str,
        stop_type: StopLossType,
        stop_percentage: float,
        stop_offset: float
    ) -> float:
        """
        Calcule le prix de stop
        
        Args:
            current_price: Prix actuel
            side: Côté
            stop_type: Type de stop
            stop_percentage: Pourcentage
            stop_offset: Offset
            
        Returns:
            float: Prix de stop
        """
        if side.upper() == "BUY":
            multiplier = -1
        else:
            multiplier = 1
        
        if stop_type == StopLossType.FIXED:
            stop_price = current_price * (1 - multiplier * stop_percentage)
        
        elif stop_type == StopLossType.TRAILING:
            offset = stop_offset or self.config.default_offset
            if side.upper() == "BUY":
                stop_price = current_price * (1 - offset)
            else:
                stop_price = current_price * (1 + offset)
        
        elif stop_type == StopLossType.VOLATILITY:
            volatility = self._calculate_volatility(current_price)
            stop_price = current_price * (1 - multiplier * volatility)
        
        else:
            stop_price = current_price * (1 - multiplier * stop_percentage)
        
        return stop_price
    
    def _calculate_volatility(self, price: float) -> float:
        """
        Calcule la volatilité
        
        Args:
            price: Prix
            
        Returns:
            float: Volatilité
        """
        # Simulation de volatilité
        # À remplacer par un calcul réel
        return 0.02  # 2% par défaut
    
    def update_order(
        self,
        order_id: str,
        current_price: float
    ) -> bool:
        """
        Met à jour un ordre de stop loss
        
        Args:
            order_id: ID de l'ordre
            current_price: Prix actuel
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                return False
            
            if order.status != StopLossStatus.ACTIVE:
                return False
            
            # Mettre à jour les prix
            order.current_price = current_price
            
            if order.side.upper() == "BUY":
                if current_price > order.highest_price:
                    order.highest_price = current_price
            else:
                if current_price < order.lowest_price:
                    order.lowest_price = current_price
            
            # Mettre à jour le prix de stop pour trailing
            if order.type == StopLossType.TRAILING:
                self._update_trailing_stop(order)
            
            # Vérifier si le stop est déclenché
            if self._check_trigger(order):
                self._trigger_order(order_id, current_price)
                return True
            
            self._trigger_event('updated', order)
            return True
    
    def _update_trailing_stop(self, order: StopLossOrder):
        """
        Met à jour le trailing stop
        
        Args:
            order: Ordre de stop loss
        """
        if order.side.upper() == "BUY":
            new_stop = order.highest_price * (1 - self.config.default_offset)
            if new_stop > order.stop_price:
                order.stop_price = new_stop
        else:
            new_stop = order.lowest_price * (1 + self.config.default_offset)
            if new_stop < order.stop_price:
                order.stop_price = new_stop
    
    def _check_trigger(self, order: StopLossOrder) -> bool:
        """
        Vérifie si le stop doit être déclenché
        
        Args:
            order: Ordre de stop loss
            
        Returns:
            bool: True si déclenché
        """
        if order.side.upper() == "BUY":
            if order.current_price <= order.stop_price:
                return True
        else:
            if order.current_price >= order.stop_price:
                return True
        
        # Vérifier le temps
        if order.type == StopLossType.TIME_BASED:
            elapsed = (datetime.now() - order.created_at).total_seconds()
            if elapsed >= self.config.time_based_duration:
                return True
        
        return False
    
    def _trigger_order(self, order_id: str, current_price: float) -> bool:
        """
        Déclenche un ordre de stop loss
        
        Args:
            order_id: ID de l'ordre
            current_price: Prix actuel
            
        Returns:
            bool: True si déclenché
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                return False
            
            order.status = StopLossStatus.TRIGGERED
            order.triggered_at = datetime.now()
            
            self.active_orders.pop(order_id, None)
            self.triggered_orders[order_id] = order
            self.stats['active_orders'] = len(self.active_orders)
            self.stats['triggered_orders'] = len(self.triggered_orders)
            
            self._update_stats()
            self._trigger_event('triggered', order)
            
            # Créer une alerte
            self._add_alert(
                f"Stop loss triggered: {order.symbol} @ {current_price:.2f}",
                "warning"
            )
            
            logger.info(f"Stop loss triggered: {order_id} @ {current_price:.2f}")
            return True
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Annule un ordre de stop loss
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            bool: True si annulé
        """
        with self._lock:
            order = self.orders.get(order_id)
            if not order:
                return False
            
            if order.status != StopLossStatus.ACTIVE:
                return False
            
            order.status = StopLossStatus.CANCELLED
            self.active_orders.pop(order_id, None)
            self.cancelled_orders[order_id] = order
            self.stats['active_orders'] = len(self.active_orders)
            self.stats['cancelled_orders'] = len(self.cancelled_orders)
            
            self._update_stats()
            self._trigger_event('cancelled', order)
            
            logger.info(f"Stop loss cancelled: {order_id}")
            return True
    
    def get_order(self, order_id: str) -> Optional[StopLossOrder]:
        """
        Récupère un ordre de stop loss
        
        Args:
            order_id: ID de l'ordre
            
        Returns:
            Optional[StopLossOrder]: Ordre
        """
        return self.orders.get(order_id)
    
    def get_active_orders(self) -> List[StopLossOrder]:
        """
        Récupère les ordres actifs
        
        Returns:
            List[StopLossOrder]: Ordres actifs
        """
        return list(self.active_orders.values())
    
    def get_orders_by_position(self, position_id: str) -> List[StopLossOrder]:
        """
        Récupère les ordres d'une position
        
        Args:
            position_id: ID de la position
            
        Returns:
            List[StopLossOrder]: Ordres
        """
        return [o for o in self.orders.values() if o.position_id == position_id]
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un callback
        
        Args:
            event: Événement ('triggered', 'cancelled', 'updated')
            callback: Fonction de callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_event(self, event: str, order: StopLossOrder):
        """
        Déclenche un événement
        
        Args:
            event: Événement
            order: Ordre
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ============================================================
    # ALERTS
    # ============================================================
    
    def _add_alert(self, message: str, severity: str = "info"):
        """
        Ajoute une alerte
        
        Args:
            message: Message
            severity: Sévérité
        """
        alert = {
            'timestamp': time.time(),
            'severity': severity,
            'message': message,
        }
        self.alerts.append(alert)
        
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        with self._lock:
            # Par type
            by_type = {}
            for order in self.orders.values():
                type_key = order.type.value
                by_type[type_key] = by_type.get(type_key, 0) + 1
            self.stats['by_type'] = by_type
            
            # Par action
            by_action = {}
            for order in self.orders.values():
                action_key = order.type.value
                by_action[action_key] = by_action.get(action_key, 0) + 1
            self.stats['by_action'] = by_action
            
            # Taux de succès
            total = self.stats['triggered_orders'] + self.stats['cancelled_orders']
            if total > 0:
                self.stats['success_rate'] = self.stats['triggered_orders'] / total
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return self.stats.copy()
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport
        
        Returns:
            Dict[str, Any]: Rapport
        """
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'active_orders': [
                {
                    'id': o.id,
                    'symbol': o.symbol,
                    'stop_price': o.stop_price,
                    'current_price': o.current_price,
                    'type': o.type.value,
                    'created_at': o.created_at.isoformat(),
                }
                for o in self.active_orders.values()
            ],
            'recent_triggers': [
                {
                    'id': o.id,
                    'symbol': o.symbol,
                    'stop_price': o.stop_price,
                    'triggered_at': o.triggered_at.isoformat() if o.triggered_at else None,
                }
                for o in list(self.triggered_orders.values())[-10:]
            ],
            'alerts': self.alerts[-10:],
        }
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._update_task = threading.Thread(target=self._update_loop, daemon=True)
        self._update_task.start()
        
        logger.info("StopLossManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._update_task:
            self._update_task.join(timeout=2)
        
        logger.info("StopLossManager monitoring stopped")
    
    def _update_loop(self):
        """Boucle de mise à jour"""
        while self._running:
            try:
                self._update_orders()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Update error: {e}")
                time.sleep(self.update_interval)
    
    def _update_orders(self):
        """Met à jour les ordres"""
        # À implémenter avec les prix réels
        pass

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_stop_loss_manager: Optional[StopLossManager] = None

def get_stop_loss_manager(
    config: Optional[StopLossConfig] = None
) -> StopLossManager:
    """
    Récupère le gestionnaire de stop loss (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        StopLossManager: Gestionnaire de stop loss
    """
    global _stop_loss_manager
    if _stop_loss_manager is None:
        _stop_loss_manager = StopLossManager(config)
    return _stop_loss_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'StopLossType',
    'StopLossStatus',
    'StopLossAction',
    'StopLossLevel',
    'StopLossOrder',
    'StopLossConfig',
    'StopLossManager',
    'get_stop_loss_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Stop loss manager module initialized")
